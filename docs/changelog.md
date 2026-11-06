# Changelog

## 0.5.0 (unreleased)

0.5.0 never shipped, so the research-driven changes below fold into
it. All twelve skills share the pack version; per-skill versioning
is a post-1.0 change.

- **bot-dashboard** (new skill): one-screen layout, per-widget
  polling, FastAPI + Pydantic production server, Discord OAuth2
  login gated by guild and role, the events endpoint, watch/notify,
  environment-variable table, server-only vs browser rules, licence
  safety, and a security checklist. Chart.js is the default chart;
  ApexCharts is only ever named with its licence note.
- **economy-database**: atomic compare-and-swap transfers, the
  revision feed (global sequence + per-user version, compensating
  rows instead of edits), migrations discipline with
  `scripts/migrate.py` and a shadow-DB drift check, backups via the
  backup API with verification and a portable dump, dashboard
  read-only rules, `/daily` wiring, and a race test that fails a
  naive check-then-insert.
- **testing**: the ping sample now runs against the starter bot's
  own pattern with a proven red check, the cooldown test fixed, the
  database fence hardened, a wiring-test sketch, and pinned dev
  requirements (pytest 9.2.0, pytest-asyncio 1.4.1.post1).
- **using-discord-py-skills** (router): a verbatim first-response
  blurb, four new route rows (`newr init`, install/update skills,
  token leaked, stale dashboard numbers), and load-on-demand plus
  discovery-first as the first rules.
- **newr**: `--json` machine-readable output on every command,
  typed exit codes (0/1/2/3/4), `llms.txt` agent contract, latest
  release resolved from GitHub Releases with a 1-hour cache,
  `newr init` scaffolding, `newr add` skill scaffolding, atomic
  installs, clean errors on corrupt JSON, the detection circularity
  fix, and `newr update --check`.
- **build-discord-bot**, **interactive-components**, **starter bot**:
  discord.py pin raised to `>=2.7.1` everywhere (Components V2
  needs 2.6.0+; the pack was live-verified against 2.7.1).
- **All skills**: bodies split into `references/` under the Codex
  8 KB cap — the body stays complete and coherent, the detail lives
  in `references/`, and the router loads both.

## 0.4.0

The v0.4.0 release on GitHub. Twelve skills (eight in the README
table at the time), the `newr` installer, the starter bot, and
install verification across 32 agents.
