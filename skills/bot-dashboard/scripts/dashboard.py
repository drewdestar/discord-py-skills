#!/usr/bin/env python3
"""Runnable demo dashboard for the bot-dashboard skill. Stdlib only.

One SQLite database shared by the bot (writer) and this server
(reader). This demo is the reader: it never writes to the database
it serves, except for creating its own small demo database with
sample data on first run.

    python3 skills/bot-dashboard/scripts/dashboard.py --port 8765
    # open http://127.0.0.1:8765/

Endpoints:
    GET /          dashboard page (headline numbers + one chart area,
                   data loaded from /api/stats by the page's JS)
    GET /health    {"ok": true, "db": "ok"} with HTTP 200 only when the
                   database answers a trivial query; anything else is
                   a 500. A health endpoint that always returns 200
                   proves nothing.
    GET /api/stats JSON: guild_count, member_total, commands_today,
                   top_commands, commands_by_day. Read-only.

LOCAL DEMO ONLY. Binds 127.0.0.1 and has NO login. Do not expose it
to the internet. Before any dashboard leaves localhost, the Auth
section of skills/bot-dashboard/SKILL.md (Discord OAuth2, staff
role gate) is mandatory, not optional.

Theme: the page's CSS variables come from design-with-hallmark's
dashboard_tokens() (theme "console" by default, --theme to pick
another). If Hallmark is not installed, the documented fallback is
used: one neutral palette plus one accent.
"""

import argparse
import html
import json
import sqlite3
import sys
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_THEME = "console"

# The demo database lives next to this script and is created with
# sample data on first run. *.db is gitignored in this repo.
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "dashboard_demo.db"

# Fallback palette (skill's documented fallback when Hallmark is not
# installed): one neutral palette plus one accent. Ink on paper is
# #1a1a1a on #ffffff, ~17.4:1, well above the 4.5:1 body-text bar;
# muted #71717a on #ffffff is ~4.8:1, also above it.
FALLBACK_TOKENS = {
    "--color-paper": "#ffffff",
    "--color-paper-2": "#f4f4f5",
    "--color-paper-3": "#e4e4e7",
    "--color-ink": "#1a1a1a",
    "--color-ink-2": "#3f3f46",
    "--color-muted": "#71717a",
    "--color-rule": "#d4d4d8",
    "--color-accent": "#2563eb",
    "--color-accent-ink": "#ffffff",
    "--color-focus": "#2563eb",
}

# Sample guilds: (name, member_count).
SAMPLE_GUILDS = [
    ("NEWR LABS", 128),
    ("Bot Test Server", 57),
    ("Friends & Games", 23),
]

# Sample command usage: (days_ago, command, uses). Day 0 is today,
# so the demo always has a nonzero "commands today" on first run,
# and a full 7-day series for the chart.
SAMPLE_USAGE = [
    (0, "ping", 42), (0, "help", 18), (0, "play", 15),
    (0, "balance", 11), (0, "leaderboard", 7),
    (1, "ping", 35), (1, "help", 14), (1, "play", 12),
    (1, "balance", 9), (1, "leaderboard", 5),
    (2, "ping", 38), (2, "help", 16), (2, "play", 10),
    (2, "balance", 8), (2, "leaderboard", 6),
    (3, "ping", 30), (3, "help", 12), (3, "play", 14),
    (3, "balance", 7), (3, "leaderboard", 4),
    (4, "ping", 44), (4, "help", 20), (4, "play", 9),
    (4, "balance", 10), (4, "leaderboard", 8),
    (5, "ping", 28), (5, "help", 11), (5, "play", 13),
    (5, "balance", 6), (5, "leaderboard", 3),
    (6, "ping", 33), (6, "help", 15), (6, "play", 11),
    (6, "balance", 9), (6, "leaderboard", 5),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS guilds (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    member_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS command_usage (
    command TEXT NOT NULL,
    used_on TEXT NOT NULL,
    uses INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (command, used_on)
);
"""


def ensure_demo_db(path):
    """Create a demo database with sample data if it does not exist.

    Only ever called for the default demo path (or an explicit path
    the caller asked to seed). Never called for a --db the user
    pointed at an existing database: pointing at a missing database
    must stay missing, so /health can report 500 for it.
    """
    path = Path(path)
    if path.exists():
        return path
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO guilds (name, member_count) VALUES (?, ?)",
            SAMPLE_GUILDS,
        )
        today = date.today()
        conn.executemany(
            "INSERT INTO command_usage (command, used_on, uses)"
            " VALUES (?, ?, ?)",
            [
                (cmd, (today - timedelta(days=ago)).isoformat(), uses)
                for ago, cmd, uses in SAMPLE_USAGE
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _read_only_connection(path):
    """A read-only SQLite connection. Opening a missing database
    read-only raises instead of creating an empty file, which is
    what makes /health go 500 for a missing database."""
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_db(path):
    """True only if the database answers a trivial query right now.

    The query must actually read the database file: a bare
    SELECT 1 never touches the file, so it would report 200 for a
    file of garbage bytes. Reading sqlite_master forces SQLite to
    open and parse the schema, and works on any valid SQLite
    database regardless of its tables."""
    try:
        with _read_only_connection(path) as conn:
            conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
    except (sqlite3.Error, OSError, ValueError):
        return False
    return True


def read_stats(path):
    """Read the dashboard numbers. Read-only: the connection is
    opened mode=ro, so this cannot write even by accident."""
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=6)).isoformat()
    with _read_only_connection(path) as conn:
        guild_count = conn.execute(
            "SELECT COUNT(*) AS n FROM guilds").fetchone()["n"]
        member_total = conn.execute(
            "SELECT COALESCE(SUM(member_count), 0) AS n FROM guilds"
        ).fetchone()["n"]
        commands_today = conn.execute(
            "SELECT COALESCE(SUM(uses), 0) AS n FROM command_usage"
            " WHERE used_on = ?", (today,)).fetchone()["n"]
        top_commands = [
            {"command": row["command"], "uses": row["uses"]}
            for row in conn.execute(
                "SELECT command, uses FROM command_usage"
                " WHERE used_on = ? ORDER BY uses DESC, command ASC"
                " LIMIT 5", (today,))
        ]
        commands_by_day = [
            {"day": row["used_on"], "uses": row["uses"]}
            for row in conn.execute(
                "SELECT used_on, SUM(uses) AS uses FROM command_usage"
                " WHERE used_on >= ? GROUP BY used_on ORDER BY used_on ASC",
                (week_ago,))
        ]
    return {
        "guild_count": guild_count,
        "member_total": member_total,
        "commands_today": commands_today,
        "top_commands": top_commands,
        "commands_by_day": commands_by_day,
    }


def load_theme_tokens(slug):
    """CSS variables from design-with-hallmark's dashboard_tokens(),
    or the documented neutral-plus-one-accent fallback when Hallmark
    is not installed or the slug is unknown."""
    hallmark_dir = (
        Path(__file__).resolve().parent.parent.parent
        / "design-with-hallmark" / "scripts"
    )
    if str(hallmark_dir) not in sys.path:
        sys.path.insert(0, str(hallmark_dir))
    try:
        from hallmark_theme import dashboard_tokens  # noqa: E402
        return dict(dashboard_tokens(slug))
    except Exception:
        return dict(FALLBACK_TOKENS)


def render_page(theme_slug=DEFAULT_THEME):
    """The dashboard page. Headline numbers plus one chart area;
    the numbers are loaded from /api/stats by the page's JS and
    refreshed every 10 seconds (polling, the skill's default)."""
    tokens = load_theme_tokens(theme_slug)
    css_vars = "\n".join(
        "    %s: %s;" % (name, value) for name, value in tokens.items())
    # Tokens come from our own theme data, but escape anyway: a
    # theme value must never be able to break out of the style block.
    css_vars = html.escape(css_vars, quote=False)
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot Dashboard</title>
<style>
:root {
%s
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--color-paper);
  color: var(--color-ink);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.5;
}
:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px; }
main { max-width: 960px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
header { display: flex; align-items: baseline; gap: 0.75rem; flex-wrap: wrap; }
h1 { font-size: 1.5rem; margin: 0; }
.status { display: inline-flex; align-items: center; gap: 0.4rem;
  color: var(--color-muted); font-size: 0.9rem; }
.status svg { flex: none; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem; margin: 1.5rem 0; }
.card { background: var(--color-paper-2); border: 1px solid var(--color-rule);
  border-radius: 8px; padding: 1rem 1.25rem; }
.card .label { color: var(--color-muted); font-size: 0.85rem;
  text-transform: uppercase; letter-spacing: 0.04em; }
.card .value { font-size: 2rem; font-weight: 700; line-height: 1.2; }
.card .delta { font-size: 0.9rem; color: var(--color-muted); }
.card .delta.up { color: var(--color-accent); }
section { margin-top: 2rem; }
h2 { font-size: 1.1rem; margin: 0 0 0.75rem; }
.chart { display: flex; align-items: flex-end; gap: 0.5rem; height: 180px;
  background: var(--color-paper-2); border: 1px solid var(--color-rule);
  border-radius: 8px; padding: 1rem; }
.bar-wrap { flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: flex-end; height: 100%%; min-width: 0; }
.bar { width: 100%%; max-width: 56px; background: var(--color-accent);
  border-radius: 4px 4px 0 0; transition: height 0.3s ease; }
.bar-label { font-size: 0.75rem; color: var(--color-muted); margin-top: 0.4rem;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%%; }
.bar-value { font-size: 0.8rem; font-weight: 600; }
table { width: 100%%; border-collapse: collapse; }
th, td { text-align: left; padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--color-rule); }
th { color: var(--color-muted); font-size: 0.85rem; text-transform: uppercase;
  letter-spacing: 0.04em; }
td.num, th.num { text-align: right; }
.empty, .error { color: var(--color-muted); padding: 1rem 0; }
button { background: var(--color-accent); color: var(--color-accent-ink);
  border: none; border-radius: 6px; padding: 0.5rem 1rem; font: inherit;
  cursor: pointer; }
button:hover { filter: brightness(1.08); }
footer { margin-top: 2.5rem; color: var(--color-muted); font-size: 0.85rem; }
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
</style>
</head>
<body>
<main>
  <header>
    <h1>Bot Dashboard</h1>
    <span class="status">
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
        <circle cx="5" cy="5" r="5" fill="var(--color-accent)"/>
      </svg>
      <span id="status-text">Loading&hellip;</span>
    </span>
    <span style="flex: 1"></span>
    <button id="refresh" type="button">Refresh</button>
  </header>

  <div class="stats" aria-live="polite">
    <div class="card">
      <div class="label">Guilds</div>
      <div class="value" id="guild-count">&hellip;</div>
    </div>
    <div class="card">
      <div class="label">Members</div>
      <div class="value" id="member-total">&hellip;</div>
    </div>
    <div class="card">
      <div class="label">Commands today</div>
      <div class="value" id="commands-today">&hellip;</div>
      <div class="delta" id="commands-delta"></div>
    </div>
  </div>

  <section aria-labelledby="chart-heading">
    <h2 id="chart-heading">Commands per day, last 7 days</h2>
    <div class="chart" id="chart">
      <p class="empty">Loading chart&hellip;</p>
    </div>
  </section>

  <section aria-labelledby="top-heading">
    <h2 id="top-heading">Top commands today</h2>
    <div id="top-commands"><p class="empty">Loading&hellip;</p></div>
  </section>

  <footer>Local demo only &mdash; binds 127.0.0.1, no login.
  Polls /api/stats every 10 seconds.</footer>
</main>
<script>
async function loadStats() {
  const status = document.getElementById("status-text");
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    status.textContent = "Live";
    document.getElementById("guild-count").textContent = data.guild_count;
    document.getElementById("member-total").textContent = data.member_total;
    document.getElementById("commands-today").textContent = data.commands_today;

    const byDay = data.commands_by_day || [];
    const deltaEl = document.getElementById("commands-delta");
    if (byDay.length >= 2) {
      const today = byDay[byDay.length - 1].uses;
      const yesterday = byDay[byDay.length - 2].uses;
      const diff = today - yesterday;
      const sign = diff > 0 ? "+" : diff < 0 ? "\\u2212" : "";
      deltaEl.textContent = sign + Math.abs(diff) + " vs yesterday";
      deltaEl.classList.toggle("up", diff > 0);
    } else {
      deltaEl.textContent = "";
    }

    const chart = document.getElementById("chart");
    if (!byDay.length || data.commands_today === 0) {
      chart.innerHTML = '<p class="empty">No commands yet today &mdash; ' +
        'try /ping in your server.</p>';
    } else {
      const max = Math.max(...byDay.map(d => d.uses), 1);
      chart.innerHTML = byDay.map(d => {
        const pct = Math.round((d.uses / max) * 100);
        const label = d.day.slice(5);
        return '<div class="bar-wrap">' +
          '<span class="bar-value">' + d.uses + '</span>' +
          '<div class="bar" style="height: ' + pct + '%%" ' +
          'role="img" aria-label="' + d.day + ': ' + d.uses + ' commands"></div>' +
          '<span class="bar-label">' + label + '</span></div>';
      }).join("");
    }

    const top = document.getElementById("top-commands");
    if (!data.top_commands || !data.top_commands.length) {
      top.innerHTML = '<p class="empty">No commands yet today &mdash; ' +
        'try /ping in your server.</p>';
    } else {
      top.innerHTML = '<table><thead><tr><th>Command</th>' +
        '<th class="num">Uses</th></tr></thead><tbody>' +
        data.top_commands.map(c =>
          '<tr><td>/' + c.command + '</td><td class="num">' + c.uses +
          '</td></tr>').join("") + '</tbody></table>';
    }
  } catch (err) {
    status.textContent = "Could not load stats";
    document.getElementById("chart").innerHTML =
      '<p class="error">Could not load stats (' + err.message +
      '). Is the demo server still running?</p>';
  }
}
document.getElementById("refresh").addEventListener("click", loadStats);
loadStats();
setInterval(loadStats, 10000);
</script>
</body>
</html>
""" % css_vars


class DashboardHandler(BaseHTTPRequestHandler):
    """Serves /, /health and /api/stats. Reads the database only,
    through read-only connections, and never writes to it."""

    db_path = DEFAULT_DB_PATH
    theme_slug = DEFAULT_THEME
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep test output readable
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status, body):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self._send_html(200, render_page(self.theme_slug))
        elif self.path == "/health":
            # A fresh trivial query on every request: a dead or
            # missing database must flip this to 500 immediately.
            if check_db(self.db_path):
                self._send_json(200, {"ok": True, "db": "ok"})
            else:
                self._send_json(500, {"ok": False, "db": "error"})
        elif self.path == "/api/stats":
            try:
                self._send_json(200, read_stats(self.db_path))
            except (sqlite3.Error, OSError, ValueError):
                self._send_json(500, {"ok": False, "error": "db_unavailable"})
        else:
            self._send_json(404, {"ok": False, "error": "not_found"})


def create_server(port, db_path, theme_slug=DEFAULT_THEME):
    """Build (do not start) the dashboard server. The caller owns
    serve_forever() / shutdown(). Used by the tests to boot the
    server on an ephemeral port in a thread."""

    class Handler(DashboardHandler):
        pass

    Handler.db_path = Path(db_path)
    Handler.theme_slug = theme_slug
    return ThreadingHTTPServer((HOST, port), Handler)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Local demo dashboard for the bot-dashboard skill.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="port to listen on (default %(default)s)")
    parser.add_argument("--db", type=Path, default=None,
                        help="SQLite database to read. Default: a demo"
                        " database created next to this script on first"
                        " run. Pointing at a missing database is not"
                        " auto-created: /health reports 500 for it.")
    parser.add_argument("--theme", default=DEFAULT_THEME,
                        help="Hallmark theme slug for the page colours"
                        " (default %(default)s); falls back to a neutral"
                        " palette when Hallmark is not installed.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.db is None:
        db_path = ensure_demo_db(DEFAULT_DB_PATH)
    else:
        # An explicit --db is the user's database: never create it.
        db_path = args.db
    server = create_server(args.port, db_path, args.theme)
    print("Bot dashboard demo at http://%s:%d/ (db: %s)"
          % (HOST, server.server_address[1], db_path), flush=True)
    print("Local demo only: no login, binds 127.0.0.1. Do not expose it.",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
