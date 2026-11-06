#!/usr/bin/env python3
"""Tests for the bot-dashboard skill and its demo server.

The demo server is booted for real on an ephemeral localhost port
and hit over HTTP with urllib. No Discord token, no network calls
to Discord, no pip packages: Python standard library only.

Run from the repo root with:
    python3 -m unittest tests.test_bot_dashboard -v
"""

import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SKILL = REPO / "skills" / "bot-dashboard" / "SKILL.md"
SCRIPT = REPO / "skills" / "bot-dashboard" / "scripts" / "dashboard.py"

# The seeded demo data: 3 guilds, 208 members, 93 commands today.
EXPECTED_GUILD_COUNT = 3
EXPECTED_MEMBER_TOTAL = 128 + 57 + 23
EXPECTED_COMMANDS_TODAY = 42 + 18 + 15 + 11 + 7


def load_demo_module():
    spec = importlib.util.spec_from_file_location("bot_dashboard_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _split_frontmatter(text):
    if not text.startswith("---\n"):
        raise AssertionError("missing frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise AssertionError("unterminated frontmatter")
    meta = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[end + 5:]


class DemoServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "demo.db"
        self.demo = load_demo_module()
        self.demo.ensure_demo_db(self.db_path)
        self.server = self.demo.create_server(0, self.db_path)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def _get(self, path, port=None):
        with urllib.request.urlopen(
            "http://127.0.0.1:%d%s" % (port or self.port, path), timeout=5
        ) as resp:
            return resp.status, resp.headers.get_content_type(), resp.read()

    def _get_error(self, path, port=None):
        try:
            self._get(path, port=port)
        except urllib.error.HTTPError as err:
            return err.code, err.read()
        self.fail("expected HTTP error for %s" % path)

    def test_binds_localhost_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_health_ok(self):
        status, _, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True, "db": "ok"})

    def test_api_stats_shape_and_seed(self):
        status, ctype, body = self._get("/api/stats")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "application/json")
        data = json.loads(body)
        self.assertEqual(data["guild_count"], EXPECTED_GUILD_COUNT)
        self.assertEqual(data["member_total"], EXPECTED_MEMBER_TOTAL)
        self.assertEqual(data["commands_today"], EXPECTED_COMMANDS_TODAY)
        self.assertEqual(data["top_commands"][0],
                         {"command": "ping", "uses": 42})
        uses = [c["uses"] for c in data["top_commands"]]
        self.assertEqual(uses, sorted(uses, reverse=True))
        # Seven-day series for the chart, oldest first, ending today.
        self.assertEqual(len(data["commands_by_day"]), 7)
        self.assertEqual(data["commands_by_day"][-1]["day"],
                         date.today().isoformat())
        self.assertEqual(data["commands_by_day"][-1]["uses"],
                         EXPECTED_COMMANDS_TODAY)

    def test_index_serves_page(self):
        status, ctype, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "text/html")
        self.assertIn(b"Bot Dashboard", body)
        self.assertIn(b"/api/stats", body)
        # Headline numbers plus one chart area.
        self.assertIn(b"guild-count", body)
        self.assertIn(b"member-total", body)
        self.assertIn(b"commands-today", body)
        self.assertIn(b'id="chart"', body)
        self.assertIn(b"setInterval", body)
        # No login form: this is the local-only demo.
        self.assertNotIn(b"<form", body)

    def test_unknown_path_404(self):
        status, body = self._get_error("/nope")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "not_found")

    def test_health_500_when_db_missing(self):
        # Pointing at a database that does not exist must NOT create
        # it, and /health must go 500 instead of lying with 200.
        missing = Path(self.tmp.name) / "missing.db"
        server = self.demo.create_server(0, missing)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, body = self._get_error("/health", port=port)
            self.assertEqual(status, 500)
            self.assertEqual(json.loads(body), {"ok": False, "db": "error"})
            self.assertFalse(missing.exists(),
                             "serving must not create a missing database")
        finally:
            server.shutdown()
            server.server_close()

    def test_api_stats_empty_db(self):
        # A valid but empty database: zeros and empty lists, not a
        # 500. The page renders its "No commands yet today" state.
        import sqlite3

        empty = Path(self.tmp.name) / "empty.db"
        conn = sqlite3.connect(empty)
        conn.executescript(self.demo.SCHEMA)
        conn.commit()
        conn.close()
        server = self.demo.create_server(0, empty)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            _, _, body = self._get("/api/stats", port=port)
            data = json.loads(body)
            self.assertEqual(data["guild_count"], 0)
            self.assertEqual(data["member_total"], 0)
            self.assertEqual(data["commands_today"], 0)
            self.assertEqual(data["top_commands"], [])
            self.assertEqual(data["commands_by_day"], [])
        finally:
            server.shutdown()
            server.server_close()

    def test_api_stats_500_when_db_unreadable(self):
        garbage = Path(self.tmp.name) / "garbage.db"
        garbage.write_bytes(b"this is not a sqlite database")
        server = self.demo.create_server(0, garbage)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _ = self._get_error("/api/stats", port=port)
            self.assertEqual(status, 500)
        finally:
            server.shutdown()
            server.server_close()

    def test_health_500_when_db_unreadable(self):
        # A directory where the database file should be, and a file
        # of garbage bytes: sqlite cannot answer, so /health is 500.
        for bad in ("not-a-db", "garbage.db"):
            bad_path = Path(self.tmp.name) / bad
            if bad.endswith(".db"):
                bad_path.write_bytes(b"this is not a sqlite database")
            else:
                bad_path.mkdir()
            server = self.demo.create_server(0, bad_path)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever,
                                      daemon=True)
            thread.start()
            try:
                status, _ = self._get_error("/health", port=port)
                self.assertEqual(status, 500, "db path %s" % bad)
            finally:
                server.shutdown()
                server.server_close()

    def test_api_stats_never_writes(self):
        def snapshot():
            digest = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
            stat = self.db_path.stat()
            sidecars = sorted(p.name for p in Path(self.tmp.name).iterdir()
                              if p.name != self.db_path.name)
            return digest, stat.st_size, stat.st_mtime_ns, sidecars

        before = snapshot()
        for _ in range(5):
            self._get("/api/stats")
        self._get("/health")
        self._get("/")
        after = snapshot()
        self.assertEqual(before, after,
                         "serving reads must not change the database file"
                         " or create sidecar files")

    def test_demo_db_seed_is_idempotent(self):
        # Seeding twice must not duplicate guilds or usage rows.
        self.demo.ensure_demo_db(self.db_path)
        data = self.demo.read_stats(self.db_path)
        self.assertEqual(data["guild_count"], EXPECTED_GUILD_COUNT)
        self.assertEqual(data["commands_today"], EXPECTED_COMMANDS_TODAY)


class ThemeTest(unittest.TestCase):
    def test_console_theme_tokens_used(self):
        # dashboard_tokens() exists in design-with-hallmark and the
        # demo page must use it: the Console theme's paper, ink and
        # accent appear as CSS variables in the served page.
        page = load_demo_module().render_page("console")
        self.assertIn("--color-paper: #0d1013", page)
        self.assertIn("--color-ink: #eceff2", page)
        self.assertIn("--color-accent: #f7b83d", page)

    def test_unknown_theme_falls_back_to_neutral_palette(self):
        page = load_demo_module().render_page("no-such-theme")
        self.assertIn("--color-paper: #ffffff", page)
        self.assertIn("--color-accent: #2563eb", page)


class CliTest(unittest.TestCase):
    def test_cli_boots_and_serves(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "demo.db"
            load_demo_module().ensure_demo_db(db_path)
            port = free_port()
            proc = subprocess.Popen(
                [sys.executable, str(SCRIPT),
                 "--port", str(port), "--db", str(db_path)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True)
            try:
                deadline = time.time() + 15
                healthy = False
                while time.time() < deadline:
                    try:
                        with urllib.request.urlopen(
                                "http://127.0.0.1:%d/health" % port,
                                timeout=2) as resp:
                            healthy = (resp.status == 200
                                       and json.loads(resp.read())
                                       == {"ok": True, "db": "ok"})
                            break
                    except (urllib.error.URLError, OSError):
                        if proc.poll() is not None:
                            break
                        time.sleep(0.2)
                self.assertTrue(healthy, "CLI server did not become healthy")
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/api/stats" % port,
                        timeout=5) as resp:
                    data = json.loads(resp.read())
                self.assertEqual(data["guild_count"], EXPECTED_GUILD_COUNT)
                self.assertEqual(data["commands_today"],
                                 EXPECTED_COMMANDS_TODAY)
            finally:
                proc.terminate()
                proc.wait(timeout=10)

    def test_cli_missing_db_health_is_500(self):
        # The exact CLI from the skill, pointed at a missing database:
        # /health must be 500, and the file must stay missing.
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.db"
            port = free_port()
            proc = subprocess.Popen(
                [sys.executable, str(SCRIPT),
                 "--port", str(port), "--db", str(missing)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True)
            try:
                deadline = time.time() + 15
                code = None
                while time.time() < deadline:
                    try:
                        urllib.request.urlopen(
                            "http://127.0.0.1:%d/health" % port, timeout=2)
                    except urllib.error.HTTPError as err:
                        code = err.code
                        break
                    except (urllib.error.URLError, OSError):
                        if proc.poll() is not None:
                            break
                        time.sleep(0.2)
                self.assertEqual(code, 500,
                                 "CLI /health must be 500 for a missing DB")
                self.assertFalse(missing.exists())
            finally:
                proc.terminate()
                proc.wait(timeout=10)


class SkillFileTest(unittest.TestCase):
    def test_frontmatter(self):
        text = SKILL.read_text(encoding="utf-8")
        meta, body = _split_frontmatter(text)
        self.assertEqual(meta.get("name"), "bot-dashboard")
        desc = meta.get("description", "")
        self.assertGreaterEqual(len(desc), 1)
        self.assertLessEqual(len(desc), 1024)
        self.assertIn("Use when", desc)
        self.assertIn("license", meta)
        self.assertIn("compatibility", meta)
        self.assertLess(len(body.splitlines()), 500)

    def test_body_covers_the_essentials(self):
        # The skill is SKILL.md plus its references/ files: the long
        # sections live there, so the essentials check reads all of
        # them, not just the body.
        skill_dir = SKILL.parent
        text = SKILL.read_text(encoding="utf-8")
        refs_dir = skill_dir / "references"
        if refs_dir.is_dir():
            for ref in sorted(refs_dir.glob("*.md")):
                text += "\n" + ref.read_text(encoding="utf-8")
        for token in (
            "OAuth2",
            "state",
            "WAL",
            "polling",
            "SSE",
            "dashboard_tokens",
            "UNVERIFIED",
            "127.0.0.1",
            "i18n",
            "/health",
            "/api/stats",
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_script_is_stdlib_only(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for banned in ("import fastapi", "import aiohttp", "import discord",
                       "import requests", "import flask"):
            self.assertNotIn(banned, text)
        # The only cross-skill import is the Hallmark theme helper,
        # which is itself stdlib-only.
        self.assertNotIn("import aiosqlite", text)


if __name__ == "__main__":
    unittest.main()
