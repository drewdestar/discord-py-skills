## Server-only vs browser code

Draw this line before writing any dashboard code, and check
every new file against it. If a line belongs on the wrong side,
move it — do not argue it into the other column.

| Runs in the bot process (server) | Runs in the browser (client) |
|---|---|
| Discord OAuth2 exchange, session + refresh tokens | One opaque session cookie, nothing else |
| Guild / role checks, `canAccess()` decisions | Hiding a button the server already refused — display only, never a check |
| All SQLite reads and writes, via `Depends(get_db)` | `fetch()` to the skill's own `/api/*` endpoints only |
| Bot token, client secret, `DASHBOARD_SECRET` | No secret of any kind, ever |
| Named command handlers, validated by Pydantic | Named command calls (`POST /api/commands/run_command`), no raw SQL, no bot methods |
| Audit / events writes, rate limiting | Rendering state: stat cards, chart, table, toasts, empty states |

The test is one sentence: if the browser can do it without the
server, the server was not doing its job. The browser renders
state and asks for named commands; the server decides, checks,
reads, writes, and logs. Homepage's server-side proxy is the
model: the backend calls Discord's API and SQLite, the browser
only ever sees the skill's own `/api/stats`.
