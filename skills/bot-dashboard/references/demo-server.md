## The demo server

`scripts/dashboard.py` is a runnable dashboard with zero
dependencies — Python standard library only. It exists so the
pattern can be run and checked here, not just read about.

```bash
python3 skills/bot-dashboard/scripts/dashboard.py --port 8765
# open http://127.0.0.1:8765/
```

Endpoints:

| Endpoint | What it returns |
|---|---|
| `GET /` | The dashboard page: headline numbers plus one chart area, data loaded from `/api/stats`. |
| `GET /health` | `{"ok": true, "db": "ok"}` with HTTP 200 only when the database answers a trivial query. Anything else is a 500. A health endpoint that always returns 200 proves nothing. |
| `GET /api/stats` | JSON: guild count, member total, commands used today, top commands. Read-only; it never writes. |

The demo binds `127.0.0.1` only and has NO login. That is
deliberate: it is a local demo, not a deployment. Do not expose
it to the internet. Before any dashboard leaves localhost, the
Auth section (`references/auth.md`) is mandatory, not optional.

### Health, per source

`/health` in the demo checks the database only: it returns 200
when the database answers a trivial query, 500 otherwise. The
demo has no bot connection to check, so it must not claim one.
The FastAPI upgrade path adds the bot-connected variant — a
check that the bot process is reachable and the gateway is up —
but that check belongs to the FastAPI path, not the demo. The
rule underneath: every data source gets its own check, and the
page says which one is broken. A dashboard that can only say
"something is down" is half a dashboard; one that says "the
database is up, the bot gateway is down" is a dashboard that
tells you what to fix. Operators coming from frp or ClickHouse
habits may alias `/healthz` to `/health` — same handler, same
answer — but `/health` stays the canonical name; do not rename
it.
