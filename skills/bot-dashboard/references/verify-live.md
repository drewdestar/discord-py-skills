## Verify live

- Run the demo, hit `/health` and `/api/stats` from another
  shell. They return JSON with the keys the skill promises.
- Open the page at 390, 768, and 1280 widths. Nothing
  overflows, nothing clips, the headline row reads in about two
  seconds.
- Delete the database file while the server runs. `/health`
  goes 500 (and `/api/stats` too) until the server is
  restarted, which re-seeds the demo database. A health
  endpoint that stays 200 while the database is dead is lying.
  (Do not use `chmod 000` for this check: it does nothing when
  the server runs as root.)
- Try the dashboard logged out (once auth exists). It shows the
  login page and nothing else. Try it as a non-staff guild
  member. It shows "not authorized" and nothing else.
- Deploy once end to end from the written steps, on a staging
  copy if one exists. Steps that were never run are wishes, not
  a runbook.
- Open `/docs` and call `GET /api/stats` and `GET /api/events`
  from Swagger UI while logged in as staff, then as a
  non-staff guild member. Staff gets JSON; non-staff gets a
  rejection on both — if either endpoint answers a non-staff
  user, the middleware is not on that route.
- Watch the page for 70 seconds. The 10 s widgets (status,
  commands today) must move at least six times; the 60 s
  widgets (guild/member totals) must move at most twice. If
  everything refreshes together, the per-widget intervals were
  collapsed into one global timer — split them.
- Run the bot with `--nowebui` (or the FastAPI equivalent) and
  confirm the API still answers and the bot still runs, with no
  dashboard page served. Then run without it and confirm the
  page returns on the same origin, with no CORS error.
- Trigger one admin action from the dashboard and check
  `/api/events`: the new row (who, what, when) must appear
  before the success toast is believed. No row, no success.
- Revoke the staff role from a test user mid-session and call
  `/api/stats` again: it must fail. A session that survives a
  revoked role is a login-time-only check, and it fails the bar.
