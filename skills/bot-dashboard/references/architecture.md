## Architecture: one database, two processes — with a one-process variant

The bot and the API share one SQLite database. That is the whole
architecture, and it is the only sane shape for a small bot:

- The bot writes. The API reads. One writer, no lock fights.
- The database is in WAL mode with atomic transactions (see
  `economy-database`). The API never writes balances, roles, or
  anything the bot owns; it reads stats and, at most, writes to
  its own audit table.
- The bot and the API are separate processes with separate
  environments. The API process never sees the bot token. A web
  process that holds the bot token is a bot-token leak waiting
  for one bug.
- The API talks to Discord's REST API only when it must (for
  example, to check guild membership at login). It never uses the
  bot token for that; OAuth2 access tokens belong to the user
  who logged in, and they live server-side.

What this forbids, plainly: two live copies of the bot writing
to the same database (see `deploy-and-monitor`); the browser
calling the bot's database file directly; the dashboard page
embedding the bot token, a database password, or any secret in
JavaScript. A secret in the browser is a published secret.

Variant (named alternative, not the default): serve the
dashboard from the bot process itself — one process, one origin,
one SQLite DB. Open WebUI and pi-hole both prove this shape: no
CORS, no second deploy, no second database. Use it only when the
dashboard must live inside the bot process, and say so plainly:
the web code then shares the bot-token process, so a web bug is
a bot-token bug. The default stays two processes. Add a
`--nowebui`-style headless flag (SD WebUI's `--nowebui`): with
it, the bot runs the API only and serves no dashboard page;
without it, the same process serves both.
