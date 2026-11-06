## Configuration: environment variables

One process, one config source: environment variables, read once
at startup, never from the browser and never committed to the
repo. If a value is missing, fail loudly at startup — a
dashboard that silently runs without auth is worse than one
that refuses to start.

| Variable | Example | What it does |
|---|---|---|
| `DASHBOARD_HOST` | `127.0.0.1` | Bind address. `127.0.0.1` for local use; `0.0.0.0` only behind HTTPS + auth |
| `DASHBOARD_PORT` | `8765` | Port the dashboard + API listen on |
| `DASHBOARD_SECRET` | (random, 32+ chars) | Signs session cookies. Generate once, keep out of the repo |
| `DISCORD_CLIENT_ID` | `123456789012345678` | OAuth2 application id |
| `DISCORD_CLIENT_SECRET` | (from the Developer Portal) | Server-side only. Never in the browser, the logs, or the repo |
| `DISCORD_REDIRECT_URI` | `https://bot.example.com/auth/callback` | Must match the Developer Portal exactly |
| `DASHBOARD_ALLOWED_GUILDS` | `111…,222…` | Comma-separated guild ids allowed in. Empty means none, never all |
| `DASHBOARD_STAFF_ROLES` | `Moderator,Admin` | Role names (or ids) that pass the gate |
| `DASHBOARD_DB_PATH` | `./bot.db` | The one SQLite file the bot writes and the API reads |

Generate the secret with `python3 -c "import secrets;
print(secrets.token_hex(32))"` and store it the way the deployment
stores secrets — an env file with `0600` permissions, a secret
manager, never a checked-in `.env`. Rotating it logs everyone
out; that is the point.
