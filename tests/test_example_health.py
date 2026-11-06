#!/usr/bin/env python3
"""Tests for examples/health.py (deploy-and-monitor skill).

Stdlib unittest only; async cases use IsolatedAsyncioTestCase. No
Discord token, no network to Discord: the bot is never logged in, the
/health server is bound to 127.0.0.1 on an ephemeral port, and the
database is a stub probe. Run from the repo root with:
    python -m unittest tests.test_example_health -v
"""

import asyncio
import json
import logging
import math
import os
import sys
import time
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Stdlib-only stubs for discord / discord.ext / aiohttp.
#
# Repo rule: tests must run with stdlib only. Neither discord.py nor
# aiohttp is guaranteed on the machine running this file, so install
# minimal fakes into sys.modules BEFORE importing aiohttp or
# examples.health (which does ``import discord`` and
# ``from aiohttp import web``). The fakes cover exactly what
# examples/health.py and this test file use:
#   * discord.Intents.default()
#   * discord.ext.commands.Bot (is_closed/latency/user/close/run)
#   * discord.ext.tasks.loop(seconds=...) with .before_loop/.start/
#     .is_running/.cancel, running the before-loop hook up front
#   * aiohttp.web.Application/Request/Response/json_response/AppRunner/
#     TCPSite, backed by asyncio.start_server (real 127.0.0.1 TCP)
#   * aiohttp.ClientSession with ``async with session.get(url)`` and
#     resp.status / await resp.json(), backed by asyncio streams
# The stubs are installed unconditionally, so this file exercises the
# stub path even on a machine that happens to have the real packages.
# After examples.health is imported (its globals are then bound to the
# stubs), the pre-existing sys.modules entries are restored, so other
# test modules imported later in the same process still see the real
# packages (or the usual ModuleNotFoundError on a bare machine).
# ---------------------------------------------------------------------------

_STUB_MODULE_NAMES = (
    "discord",
    "discord.ext",
    "discord.ext.commands",
    "discord.ext.tasks",
    "aiohttp",
    "aiohttp.web",
)
_SAVED_MODULES = {name: sys.modules.get(name) for name in _STUB_MODULE_NAMES}


def _make_module(name, **attrs):
    module = ModuleType(name)
    module.__path__ = []
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


class _StubIntents:
    @classmethod
    def default(cls):
        return cls()


class _StubBot:
    """Minimal commands.Bot: never logged in until close() is called."""

    def __init__(self, command_prefix=None, intents=None, **_kwargs):
        self.command_prefix = command_prefix
        self.intents = intents
        self._closed = False
        self.user = None
        self.latency = float("nan")

    def is_closed(self):
        return self._closed

    async def close(self):
        self._closed = True

    def run(self, _token, **_kwargs):  # pragma: no cover - not used in tests
        return None

    async def setup_hook(self):
        return None


class _StubLoop:
    """Minimal discord.ext.tasks.loop: a per-instance bound loop."""

    def __init__(self, func, seconds):
        self._func = func
        self._seconds = seconds
        self._before_loop = None
        self._task = None
        self._running = False
        self._owner = None

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        bound = obj.__dict__.get(self._func.__name__)
        if bound is None:
            bound = _StubLoop(self._func, self._seconds)
            bound._before_loop = self._before_loop
            bound._owner = obj
            obj.__dict__[self._func.__name__] = bound
        return bound

    def before_loop(self, coro):
        self._before_loop = coro
        return coro

    def is_running(self):
        return self._running

    def start(self):
        if self._running:
            return self._task
        self._running = True

        async def _run():
            try:
                if self._before_loop is not None:
                    await self._before_loop(self._owner)
                while self._running:
                    await asyncio.sleep(self._seconds)
                    if not self._running:
                        break
                    await self._func(self._owner)
            except asyncio.CancelledError:
                raise
            finally:
                self._running = False

        self._task = asyncio.create_task(_run())
        return self._task

    def cancel(self):
        self._running = False
        if self._task is not None:
            self._task.cancel()

    def stop(self):
        self.cancel()


def _stub_tasks_loop(*, seconds=60, **_kwargs):
    def decorator(func):
        return _StubLoop(func, seconds)

    return decorator


class _StubRequest:
    def __init__(self, method, path):
        self.method = method
        self.path = path
        self.headers = {}


class _StubResponse:
    def __init__(self, body=b"", status=200, content_type="text/plain"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.body = body
        self.status = status
        self.content_type = content_type

    async def text(self):
        return self.body.decode("utf-8")


def _stub_json_response(data, status=200):
    return _StubResponse(
        json.dumps(data).encode("utf-8"),
        status=status,
        content_type="application/json",
    )


class _StubRouter:
    def __init__(self, app):
        self._app = app

    def add_get(self, path, handler):
        self._app._routes[("GET", path)] = handler


class _StubApplication:
    def __init__(self, **_kwargs):
        self._routes = {}
        self.router = _StubRouter(self)


class _StubAppRunner:
    def __init__(self, app):
        self._app = app
        self._servers = []

    @property
    def addresses(self):
        addresses = []
        for server in self._servers:
            for sock in server.sockets or []:
                addresses.append(sock.getsockname())
        return addresses

    async def setup(self):
        await asyncio.sleep(0)

    async def cleanup(self):
        for server in self._servers:
            server.close()
            await server.wait_closed()
        self._servers = []


class _StubTCPSite:
    def __init__(self, runner, host, port):
        self._runner = runner
        self._host = host
        self._port = port
        self._server = None

    async def start(self):
        # asyncio.start_server raises OSError on a port conflict, which
        # examples/health.py catches and logs (test_health_port_conflict).
        self._server = await asyncio.start_server(
            self._handle, self._host, self._port
        )
        self._runner._servers.append(self._server)

    async def _handle(self, reader, writer):
        try:
            raw = await reader.readuntil(b"\r\n\r\n")
        except (asyncio.IncompleteReadError, ConnectionError):
            writer.close()
            return
        try:
            request_line = raw.split(b"\r\n", 1)[0].decode("iso-8859-1")
            parts = request_line.split()
            method = parts[0] if parts else "GET"
            target = parts[1] if len(parts) > 1 else "/"
        except (IndexError, UnicodeDecodeError):
            writer.close()
            return
        path = urlparse(target).path
        handler = self._runner._app._routes.get((method, path))
        if handler is None:
            status, body, content_type = 404, b"Not Found", "text/plain"
        else:
            response = await handler(_StubRequest(method, path))
            status, body = response.status, response.body
            content_type = getattr(response, "content_type", "application/json")
        reason = {200: "OK", 404: "Not Found", 503: "Service Unavailable"}.get(
            status, ""
        )
        header = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("iso-8859-1")
        try:
            writer.write(header + body)
            await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()


class _StubClientResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def json(self):
        return json.loads(self._body.decode("utf-8"))

    async def text(self):
        return self._body.decode("utf-8")

    async def read(self):
        return self._body


class _StubClientRequestContext:
    def __init__(self, url):
        self._url = url

    async def __aenter__(self):
        parsed = urlparse(self._url)
        host, port = parsed.hostname, parsed.port or 80
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        reader, writer = await asyncio.open_connection(host, port)
        try:
            writer.write(
                (
                    f"GET {path} HTTP/1.1\r\n"
                    f"Host: {host}:{port}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("iso-8859-1")
            )
            await writer.drain()
            status_line = await reader.readline()
            status = int(status_line.split()[1])
            headers = {}
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break
                key, _, value = line.decode("iso-8859-1").partition(":")
                headers[key.strip().lower()] = value.strip()
            if "content-length" in headers:
                body = await reader.readexactly(int(headers["content-length"]))
            else:
                body = await reader.read()
        finally:
            writer.close()
        return _StubClientResponse(status, body)

    async def __aexit__(self, *exc):
        return False


class _StubClientSession:
    def __init__(self, *args, **kwargs):
        pass

    def get(self, url, **_kwargs):
        return _StubClientRequestContext(url)

    async def close(self):
        await asyncio.sleep(0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
        return False


def _install_stubs():
    discord_mod = _make_module("discord", Intents=_StubIntents)
    ext_mod = _make_module("discord.ext")
    commands_mod = _make_module("discord.ext.commands", Bot=_StubBot)
    tasks_mod = _make_module("discord.ext.tasks", loop=_stub_tasks_loop)
    web_mod = _make_module(
        "aiohttp.web",
        Application=_StubApplication,
        Request=_StubRequest,
        Response=_StubResponse,
        json_response=_stub_json_response,
        AppRunner=_StubAppRunner,
        TCPSite=_StubTCPSite,
    )
    aiohttp_mod = _make_module(
        "aiohttp", ClientSession=_StubClientSession, web=web_mod
    )
    ext_mod.commands = commands_mod
    ext_mod.tasks = tasks_mod
    discord_mod.ext = ext_mod
    for name, module in (
        ("discord", discord_mod),
        ("discord.ext", ext_mod),
        ("discord.ext.commands", commands_mod),
        ("discord.ext.tasks", tasks_mod),
        ("aiohttp", aiohttp_mod),
        ("aiohttp.web", web_mod),
    ):
        sys.modules[name] = module


_install_stubs()

import aiohttp  # noqa: E402  (stub installed above)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from examples.health import (  # noqa: E402
    HEARTBEAT_MAX_AGE_SECONDS,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    SYSTEMD_UNIT,
    WATCHDOG_SCRIPT,
    HealthBot,
    HealthChecker,
    configure_logging,
    evaluate_heartbeat,
    make_health_app,
    watchdog_should_restart,
    write_heartbeat,
)

# examples.health is now bound to the stubs above; restore whatever
# sys.modules held before, so later test modules in the same process
# still see the real packages (or the usual import error on a bare VM).
for _name, _module in _SAVED_MODULES.items():
    if _module is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _module
del _name, _module


def make_bot_stub(*, closed=False, latency=0.042, user=True):
    """A duck-typed stand-in for a discord.py Bot."""
    return SimpleNamespace(
        is_closed=lambda: closed,
        latency=latency,
        user=SimpleNamespace(id=123) if user else None,
    )


class TestHeartbeatFile(unittest.TestCase):
    def test_write_creates_file_with_current_timestamp(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data" / "heartbeat"
            before = int(time.time())
            written = write_heartbeat(path)
            after = int(time.time())
            self.assertTrue(path.is_file())
            self.assertEqual(int(path.read_text(encoding="utf-8")), written)
            self.assertGreaterEqual(written, before)
            self.assertLessEqual(written, after)

    def test_write_leaves_no_temp_file_behind(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heartbeat"
            write_heartbeat(path)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["heartbeat"])

    def test_write_updates_timestamp_on_rewrite(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heartbeat"
            write_heartbeat(path)
            old_mtime = path.stat().st_mtime
            os.utime(path, (time.time() - 120, time.time() - 120))
            write_heartbeat(path)
            self.assertGreater(path.stat().st_mtime, old_mtime)
            self.assertAlmostEqual(int(path.read_text()), time.time(), delta=2)


class TestEvaluateHeartbeat(unittest.TestCase):
    def test_missing_file_is_missing_and_needs_restart(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            status, age = evaluate_heartbeat(Path(tmp) / "nope")
            self.assertEqual(status, "missing")
            self.assertIsNone(age)
            self.assertTrue(watchdog_should_restart(Path(tmp) / "nope"))

    def test_fresh_file_is_ok(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heartbeat"
            path.write_text(str(int(time.time())))
            now = time.time()
            status, age = evaluate_heartbeat(path, now=now)
            self.assertEqual(status, "ok")
            self.assertGreaterEqual(age, 0)
            self.assertLess(age, 5)
            self.assertFalse(watchdog_should_restart(path, now=now))

    def test_stale_file_is_stale_and_needs_restart(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heartbeat"
            path.write_text("1")
            mtime = time.time() - 600
            os.utime(path, (mtime, mtime))
            status, age = evaluate_heartbeat(path)
            self.assertEqual(status, "stale")
            self.assertAlmostEqual(age, 600, delta=2)
            self.assertTrue(watchdog_should_restart(path))

    def test_boundary_exactly_300_seconds_is_ok(self):
        # The skill's watchdog uses -gt 300, so age == 300 is not stale.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heartbeat"
            path.write_text("1")
            mtime = 1_700_000_000.0
            os.utime(path, (mtime, mtime))
            self.assertEqual(
                evaluate_heartbeat(path, now=mtime + 300), ("ok", 300.0)
            )
            self.assertEqual(
                evaluate_heartbeat(path, now=mtime + 301)[0], "stale"
            )

    def test_future_timestamp_is_ok_not_negative_stale(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heartbeat"
            path.write_text("1")
            mtime = time.time() + 60
            os.utime(path, (mtime, mtime))
            status, age = evaluate_heartbeat(path)
            self.assertEqual(status, "ok")
            self.assertLess(age, 0)


class TestHealthChecker(unittest.IsolatedAsyncioTestCase):
    async def test_healthy_bot_with_working_db_returns_200(self):
        checker = HealthChecker(make_bot_stub(), db_probe=AsyncMock(return_value=1))
        status, payload = await checker.check()
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["checks"], {"discord_connected": True, "database_ok": True}
        )
        self.assertEqual(payload["latency_ms"], 42.0)
        self.assertIsInstance(payload["uptime_seconds"], int)
        self.assertGreaterEqual(payload["uptime_seconds"], 0)

    async def test_never_logged_in_bot_returns_503(self):
        # A fresh Bot has user None and latency nan: the endpoint must
        # not call that healthy. This is the "always 200 proves
        # nothing" case.
        checker = HealthChecker(make_bot_stub(latency=math.nan, user=False))
        status, payload = await checker.check()
        self.assertEqual(status, 503)
        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["checks"]["discord_connected"])
        self.assertIsNone(payload["latency_ms"])

    async def test_closed_bot_returns_503(self):
        checker = HealthChecker(make_bot_stub(closed=True))
        status, payload = await checker.check()
        self.assertEqual(status, 503)
        self.assertFalse(payload["checks"]["discord_connected"])

    async def test_failing_db_probe_returns_503(self):
        checker = HealthChecker(
            make_bot_stub(), db_probe=AsyncMock(return_value=0)
        )
        status, payload = await checker.check()
        self.assertEqual(status, 503)
        self.assertFalse(payload["checks"]["database_ok"])
        self.assertEqual(payload["database"], "failed")

    async def test_db_probe_exception_returns_503_not_crash(self):
        probe = AsyncMock(side_effect=RuntimeError("db down"))
        checker = HealthChecker(make_bot_stub(), db_probe=probe)
        status, payload = await checker.check()
        self.assertEqual(status, 503)
        self.assertFalse(payload["checks"]["database_ok"])

    async def test_no_db_probe_skips_database_check(self):
        checker = HealthChecker(make_bot_stub(), db_probe=None)
        status, payload = await checker.check()
        self.assertEqual(status, 200)
        self.assertTrue(payload["checks"]["database_ok"])
        self.assertEqual(payload["database"], "not_configured")

    async def test_uptime_counts_from_started_at(self):
        checker = HealthChecker(make_bot_stub(), started_at=time.monotonic() - 90)
        _, payload = await checker.check()
        self.assertGreaterEqual(payload["uptime_seconds"], 90)
        self.assertLess(payload["uptime_seconds"], 95)


class TestHealthEndpoint(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.stub = make_bot_stub()
        self.checker = HealthChecker(self.stub, db_probe=AsyncMock(return_value=1))
        self.runner = aiohttp.web.AppRunner(make_health_app(self.checker))
        await self.runner.setup()
        self.site = aiohttp.web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        port = self.runner.addresses[0][1]
        self.base_url = f"http://127.0.0.1:{port}"
        self.session = aiohttp.ClientSession()

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def test_health_returns_200_json_when_connected(self):
        async with self.session.get(f"{self.base_url}/health") as resp:
            self.assertEqual(resp.status, 200)
            body = await resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["checks"]["discord_connected"])

    async def test_health_flips_to_503_when_bot_disconnects(self):
        async with self.session.get(f"{self.base_url}/health") as resp:
            self.assertEqual(resp.status, 200)
        self.stub.user = None
        self.stub.latency = math.nan
        async with self.session.get(f"{self.base_url}/health") as resp:
            self.assertEqual(resp.status, 503)
            body = await resp.json()
        self.assertEqual(body["status"], "degraded")

    async def test_unknown_path_is_404_not_fake_200(self):
        async with self.session.get(f"{self.base_url}/nope") as resp:
            self.assertEqual(resp.status, 404)


class TestHealthBotWiring(unittest.IsolatedAsyncioTestCase):
    async def test_setup_hook_writes_heartbeat_and_serves_honest_health(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bot = HealthBot(
                heartbeat_path=Path(tmp) / "data" / "heartbeat",
                health_port=0,
            )
            try:
                await bot.setup_hook()
                # Heartbeat exists from boot, before the first 60s tick.
                self.assertTrue(bot.heartbeat_path.is_file())
                self.assertAlmostEqual(
                    int(bot.heartbeat_path.read_text()), time.time(), delta=2
                )
                self.assertTrue(bot.heartbeat_loop.is_running())
                self.assertIsNotNone(bot.health_listen_address)
                host, port = bot.health_listen_address
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://{host}:{port}/health"
                    ) as resp:
                        # Real bot, never logged in: must be 503.
                        self.assertEqual(resp.status, 503)
                        body = await resp.json()
                self.assertEqual(body["status"], "degraded")
            finally:
                await bot.close()
            # Cancellation is delivered on the next loop turn.
            await asyncio.sleep(0.1)
            self.assertFalse(bot.heartbeat_loop.is_running())
            self.assertIsNone(bot.health_listen_address)
            self.assertTrue(bot.is_closed())

    async def test_health_port_conflict_does_not_kill_bot(self):
        import tempfile

        blocker = aiohttp.web.AppRunner(aiohttp.web.Application())
        await blocker.setup()
        site = aiohttp.web.TCPSite(blocker, "127.0.0.1", 0)
        await site.start()
        busy_port = blocker.addresses[0][1]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                bot = HealthBot(
                    heartbeat_path=Path(tmp) / "heartbeat",
                    health_port=busy_port,
                )
                try:
                    await bot.setup_hook()
                    self.assertTrue(bot.heartbeat_loop.is_running())
                    self.assertIsNone(bot.health_listen_address)
                finally:
                    await bot.close()
        finally:
            await blocker.cleanup()


class TestRunbookArtifacts(unittest.TestCase):
    def test_systemd_unit_has_supervisor_settings(self):
        for line in (
            "Restart=always",
            "RestartSec=10",
            "EnvironmentFile=/opt/bots/mybot/.env",
            "Type=simple",
            "WorkingDirectory=/opt/bots/mybot",
        ):
            self.assertIn(line, SYSTEMD_UNIT)
        # The token lives in the EnvironmentFile, never in the unit.
        self.assertNotIn("DISCORD_TOKEN=", SYSTEMD_UNIT)

    def test_watchdog_script_matches_skill(self):
        self.assertIn("systemctl restart mybot", WATCHDOG_SCRIPT)
        self.assertIn('"$AGE"', WATCHDOG_SCRIPT)
        self.assertIn("-gt 300", WATCHDOG_SCRIPT)
        self.assertNotIn("kill -9", WATCHDOG_SCRIPT)
        self.assertNotIn("kill -9", SYSTEMD_UNIT)

    def test_log_rotation_matches_skill(self):
        self.assertEqual(LOG_MAX_BYTES, 10 * 1024 * 1024)
        self.assertEqual(LOG_BACKUP_COUNT, 5)

    def test_configure_logging_rotates_and_never_logs_token(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            handler = configure_logging(Path(tmp) / "logs" / "bot.log")
            try:
                self.assertEqual(handler.maxBytes, 10 * 1024 * 1024)
                self.assertEqual(handler.backupCount, 5)
                self.assertNotIn("token", handler.formatter._fmt.lower())
            finally:
                handler.close()
                logging.getLogger().removeHandler(handler)

    def test_configure_logging_twice_still_attaches_second_handler(self):
        # basicConfig is a no-op on the second call; the handler must
        # still end up on the root logger.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            first = configure_logging(Path(tmp) / "one.log")
            second = configure_logging(Path(tmp) / "two.log")
            try:
                root_handlers = logging.getLogger().handlers
                self.assertIn(first, root_handlers)
                self.assertIn(second, root_handlers)
            finally:
                for handler in (first, second):
                    handler.close()
                    logging.getLogger().removeHandler(handler)

    def test_heartbeat_constants_match_skill(self):
        self.assertEqual(HEARTBEAT_MAX_AGE_SECONDS, 300)

    def test_no_em_dash_in_example_source(self):
        # Skill quality bar: no em dash in anything the bot sends.
        # The example sends nothing, and the file keeps that bar.
        source = (REPO_ROOT / "examples" / "health.py").read_text(encoding="utf-8")
        self.assertNotIn("\u2014", source)


class TestMain(unittest.TestCase):
    def test_main_exits_without_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                from examples.health import main

                main()
        self.assertIn("DISCORD_TOKEN", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
