"""Health check and watchdog pattern (deploy-and-monitor skill).

A bot that dies at 3 AM and stays dead until someone notices is not
deployed, it is running on luck. This example wires up the three legs
the skill requires:

1. A supervisor that restarts a dead process (systemd unit below,
   ``Restart=always`` with a 10 second delay).
2. A watchdog that restarts a process that is alive but stuck: the bot
   touches a heartbeat file every 60 seconds from inside its event
   loop, and an outside watchdog restarts the service when the file
   goes stale. The heartbeat proves the event loop is alive, not just
   the process.
3. A health check probed from outside the bot: a ``/health`` endpoint
   that returns 200 only when the bot is connected to Discord AND the
   database answers a trivial query. A health endpoint that always
   returns 200 proves nothing.

Run it with ``DISCORD_TOKEN`` set in the environment. Nothing here
touches the network except the bot login and the local health server.
"""

import logging
import math
import os
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import discord
from aiohttp import web
from discord.ext import commands, tasks

log = logging.getLogger("healthbot")

HEARTBEAT_INTERVAL_SECONDS = 60
HEARTBEAT_MAX_AGE_SECONDS = 300
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5

# The token lives in the EnvironmentFile, never in this unit, and that
# file must be owned by the bot user with mode 600. A token in the unit
# itself or in a world-readable file is a leaked token.
SYSTEMD_UNIT = """[Unit]
Description=My Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=bot
WorkingDirectory=/opt/bots/mybot
EnvironmentFile=/opt/bots/mybot/.env
ExecStart=/opt/bots/mybot/.venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/mybot/bot.log
StandardError=append:/var/log/mybot/bot.log

[Install]
WantedBy=multi-user.target
"""

WATCHDOG_SCRIPT = """#!/bin/bash
# watchdog.sh, run every minute from cron
HEARTBEAT=/opt/bots/mybot/data/heartbeat
if [ ! -f "$HEARTBEAT" ]; then
  systemctl restart mybot
  exit 0
fi
AGE=$(( $(date +%s) - $(stat -c %Y "$HEARTBEAT") ))
if [ "$AGE" -gt 300 ]; then
  systemctl restart mybot
fi
"""


def configure_logging(log_path: str | Path = "logs/bot.log") -> RotatingFileHandler:
    """Log to a rotating file: 10 MB per file, 5 files kept.

    A bot that logs forever fills the disk, and a full disk kills the
    database first. Never log the token, and never log full message
    content in production unless the bot's purpose requires it.
    """
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # basicConfig is a no-op when the root logger already has handlers
    # (for example, if this is called twice), so attach explicitly
    # when it did not.
    root = logging.getLogger()
    if handler not in root.handlers:
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    return handler


def write_heartbeat(path: str | Path) -> int:
    """Touch the heartbeat file with the current timestamp, atomically.

    Writes to a sibling temp file and renames it over the target, so a
    watchdog reading the file mid-write never sees a partial value.
    Returns the timestamp written.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(str(timestamp), encoding="utf-8")
    os.replace(tmp, target)
    return timestamp


def evaluate_heartbeat(
    path: str | Path,
    max_age_seconds: int = HEARTBEAT_MAX_AGE_SECONDS,
    now: float | None = None,
) -> tuple[str, float | None]:
    """Judge a heartbeat file: ("ok", age), ("stale", age) or ("missing", None).

    Stale means older than ``max_age_seconds`` (300 seconds in the
    skill, matching the watchdog's ``-gt 300`` test). A missing file
    is its own status: the bot may never have started, which is
    different from a bot that started and then wedged.
    """
    current = time.time() if now is None else now
    try:
        mtime = Path(path).stat().st_mtime
    except FileNotFoundError:
        return ("missing", None)
    age = current - mtime
    if age > max_age_seconds:
        return ("stale", age)
    return ("ok", age)


def watchdog_should_restart(
    path: str | Path,
    max_age_seconds: int = HEARTBEAT_MAX_AGE_SECONDS,
    now: float | None = None,
) -> bool:
    """True when the watchdog must restart the service.

    Restarts on a missing heartbeat as well as a stale one: no file
    means the writer never ran, and a service that never wrote a
    heartbeat is not a healthy service.
    """
    status, _ = evaluate_heartbeat(path, max_age_seconds, now)
    return status != "ok"


class HealthChecker:
    """Decide what /health reports. Duck-typed on the bot.

    Healthy means BOTH: the bot is connected to Discord (not closed,
    logged in, and reporting a real latency) AND the database probe
    answers. ``db_probe`` is an optional async callable returning a
    truthy value, for example ``lambda: db.fetchval("SELECT 1")``.
    With no probe configured the database check is skipped, never
    assumed.
    """

    def __init__(self, bot, db_probe=None, started_at: float | None = None) -> None:
        self.bot = bot
        self.db_probe = db_probe
        self._started_at = time.monotonic() if started_at is None else started_at

    @property
    def uptime_seconds(self) -> int:
        return max(0, int(time.monotonic() - self._started_at))

    def _discord_connected(self) -> bool:
        # A fresh, never-logged-in Bot reports is_closed() == False
        # with latency nan and user None. Any one of those three
        # alone would call a dead bot healthy, so require all three.
        if self.bot.is_closed():
            return False
        if getattr(self.bot, "user", None) is None:
            return False
        return math.isfinite(self.bot.latency)

    async def check(self) -> tuple[int, dict]:
        """Return (HTTP status code, JSON payload) for /health."""
        discord_ok = self._discord_connected()
        if self.db_probe is None:
            database_ok = True
            database_state = "not_configured"
        else:
            try:
                database_ok = bool(await self.db_probe())
            except Exception:
                database_ok = False
            database_state = "ok" if database_ok else "failed"
        healthy = discord_ok and database_ok
        payload = {
            "status": "ok" if healthy else "degraded",
            "uptime_seconds": self.uptime_seconds,
            "latency_ms": (
                round(self.bot.latency * 1000, 1)
                if math.isfinite(self.bot.latency)
                else None
            ),
            "checks": {
                "discord_connected": discord_ok,
                "database_ok": database_ok,
            },
            "database": database_state,
        }
        return (200 if healthy else 503, payload)


def make_health_app(checker: HealthChecker) -> web.Application:
    """Build the aiohttp app serving GET /health from a checker."""
    app = web.Application()

    async def health_handler(request: web.Request) -> web.Response:
        status, payload = await checker.check()
        return web.json_response(payload, status=status)

    app.router.add_get("/health", health_handler)
    return app


class HealthBot(commands.Bot):
    """A bot that proves it is alive: heartbeat file plus /health."""

    def __init__(
        self,
        heartbeat_path: str | Path = "data/heartbeat",
        health_host: str = "127.0.0.1",
        health_port: int = 8080,
        db_probe=None,
    ) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.heartbeat_path = Path(heartbeat_path)
        self.health_host = health_host
        self.health_port = health_port
        self.health_checker = HealthChecker(self, db_probe=db_probe)
        self._health_runner: web.AppRunner | None = None

    @property
    def health_listen_address(self):
        """(host, port) the health server bound to, or None."""
        if self._health_runner is None:
            return None
        addresses = self._health_runner.addresses
        return addresses[0] if addresses else None

    async def setup_hook(self) -> None:
        self.heartbeat_loop.start()
        await self._start_health_server()

    async def _start_health_server(self) -> None:
        app = make_health_app(self.health_checker)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.health_host, self.health_port)
        try:
            await site.start()
        except OSError:
            log.warning(
                "Health endpoint could not bind %s:%s; continuing without it.",
                self.health_host,
                self.health_port,
            )
            await runner.cleanup()
            return
        self._health_runner = runner
        log.info(
            "Health endpoint listening on http://%s:%s/health",
            self.health_host,
            self.health_port,
        )

    @tasks.loop(seconds=HEARTBEAT_INTERVAL_SECONDS)
    async def heartbeat_loop(self) -> None:
        write_heartbeat(self.heartbeat_path)

    @heartbeat_loop.before_loop
    async def _write_heartbeat_at_startup(self) -> None:
        # The loop waits a full interval before its first tick, so
        # write once up front: the watchdog must see a fresh file
        # from boot, not after the first 60 seconds.
        write_heartbeat(self.heartbeat_path)

    async def on_ready(self) -> None:
        log.info("Logged in as %s (%s).", self.user, self.user.id)

    async def close(self) -> None:
        # Never restart with kill -9: a forced kill can interrupt a
        # database write mid-transaction. Stop the loop, drop the
        # health server, then close the Discord connection cleanly.
        #
        # cancel(), not stop(): stop() only sets a flag and the loop
        # keeps sleeping until its next 60 second tick, so close()
        # would return with the loop still running. cancel() ends it
        # at once, and that is safe here because the heartbeat write
        # is one atomic rename with no await point inside it.
        if self.heartbeat_loop.is_running():
            self.heartbeat_loop.cancel()
        if self._health_runner is not None:
            await self._health_runner.cleanup()
            self._health_runner = None
        await super().close()


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("set the DISCORD_TOKEN environment variable")
    configure_logging()
    bot = HealthBot()
    bot.run(token)


if __name__ == "__main__":
    main()
