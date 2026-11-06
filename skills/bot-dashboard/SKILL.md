---
name: bot-dashboard
description: "Build a web dashboard and backend API for a discord.py bot: one SQLite database shared by the bot and the API, Discord OAuth2 login gated by guild and role, live numbers with polling or SSE, and a one-screen layout. Use when the user says 'make a dashboard for my bot', 'web panel', 'bot website', 'let admins manage the bot from the web', or 'show bot stats on a page'. Do NOT use for the bot's Discord commands or embeds; use slash-commands, interactive-components, or design-with-hallmark for those."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, no paid services"
metadata:
  version: "0.5.0"
  author: "drewdestar"
---

# Bot Dashboard

A dashboard answers three questions on one screen: is the bot alive,
what is happening, and what needs attention. Everything else is
depth behind a tab. If a visitor cannot answer all three in about
two seconds, the dashboard failed, no matter how good it looks.

This skill teaches the web side the rest of the pack assumes exists:
`design-with-hallmark` themes a dashboard, `deploy-and-monitor`
tells you to add a `/health` endpoint to one, and neither teaches
you to build one. This one does.

## Architecture: one database, two processes — with a one-process variant

One SQLite database, two processes (bot + API), with the one-process variant. See `references/architecture.md`.

## The demo server

The demo server in `scripts/dashboard.py`: what it proves and what it does not. See `references/demo-server.md`.

## The production server: FastAPI + Pydantic + Depends

The production server: FastAPI + Pydantic + Depends, with the limiter and `/metrics`. See `references/production-server.md`.

## Auth: Discord OAuth2, done the boring way

Discord OAuth2 login gated by guild and role, the session, the allowlisted command bridge, and the WebSocket auth gotchas. See `references/auth.md`.

## Realtime: per-widget polling intervals

Per-widget polling intervals, with SSE streamed and progressive states. See `references/realtime-polling.md`.

## Realtime transport: one seam, swappable transports

Structure the live side as `Transport → codec → typed EventBus
→ reactive stores → UI`, with polling, SSE, and WebSocket as
interchangeable `Transport` implementations behind one
interface, plus a `MockTransport` for offline tests. The page
does not know or care which transport is behind the seam: the
polling transport fetches `/api/stats` and `/api/events` on the
per-widget intervals in `references/realtime-polling.md`; the SSE transport subscribes to the
events channel; the WebSocket transport does the same over a
socket. Swapping transports is a one-line change, not a rewrite,
and the UI runs against `MockTransport` with zero bot running —
which is how the page gets tested at all. This is a design
section, not a demo rewrite: the stdlib demo keeps its single
polling timer, and the seam is what you build when the
upgrade to SSE or WebSocket becomes a user-visible need.

## Layout: the one-screen dashboard

The one-screen dashboard layout, empty and loading states, toasts, and destructive actions. See `references/layout.md`.

## Revision / audit feed: the events endpoint

The events endpoint: the revision/audit feed the dashboard polls. See `references/revision-feed.md`.

## Watch / notify: the dashboard that taps you on the shoulder

Watch/notify: the dashboard that taps you on the shoulder, with trend graphs. See `references/watch-notify.md`.

## Configuration: environment variables

Environment variables for the dashboard and the bot. See `references/configuration.md`.

## Server-only vs browser code

What runs server-only and what runs in the browser. See `references/server-vs-browser.md`.

## Licence safety: patterns only, never copied code

Every repo named in this skill is a *pattern* reference, never a
code source. Steal the shape — pi-hole's one-screen layout,
Grafana's panel grid, Refine's provider split, Supabase's
channel model — and write the code yourself, in this pack, under
its MIT licence. Never vendor or copy code from an AGPL or GPL
repo into this pack or into a bot built from it: metabase,
glance, netbird, stable-diffusion-webui, firecrawl, searxng,
and scira are all AGPL-3.0 in the research, and AGPL/GPL code
copied into a shipped project carries copyleft obligations this
pack does not accept. If a pattern only exists in an AGPL repo,
describe it in your own words and implement it from the
description. When in doubt, check the repo's `LICENSE` file
before treating anything as MIT — the GitHub API reports
NOASSERTION for several of these repos, so the API's licence
field is not proof.

## Theme: one system, dealt once

Deal a Hallmark theme with `design-with-hallmark` and use its
`dashboard_tokens()` as the page's CSS variables. Do not invent
colors alongside them. The theme skill owns the look; this skill
owns the structure. If Hallmark is not installed, one neutral
palette plus one accent is the fallback — and that is a valid
subset, not a failure.

Run the dashboard through the same checks the design skills use:
contrast 4.5:1 on body text, visible focus rings, no emoji as
icons (SVG instead), cursor-pointer on clickables, text that
reflows without clipping, `prefers-reduced-motion` respected,
and the page checked at 390, 768, and 1280 widths. Motion is a
token (one duration family), not a one-off, and it stops entirely
under reduced motion.

## Security checklist (before the dashboard leaves localhost)

The security checklist before the dashboard leaves localhost. See `references/security-checklist.md`.

## Cross-platform and all-languages box

Cross-platform and all-languages notes. See `references/cross-platform.md`.

## Verify live

How to verify the dashboard live, step by step. See `references/verify-live.md`.

## What this skill never does

- It never teaches Discord commands, embeds, or components.
  Those are `slash-commands` and `interactive-components`.
- It never themes a page. That is `design-with-hallmark`.
- It never runs a bot 24/7. That is `deploy-and-monitor`.
- It never stores user data. The dashboard reads the bot's
  database; it does not become a second database.
- It never claims a check it did not run. If the FastAPI path,
  the browser widths, macOS, or Windows were not verified, the
  skill says UNVERIFIED and the agent says so to the user too.
