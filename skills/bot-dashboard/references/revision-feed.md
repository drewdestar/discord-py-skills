## Revision / audit feed: the events endpoint

The dashboard needs a memory, not just a snapshot. Add
`GET /api/events?limit=50` — the newest events first, each one
`{ id, at, type, actor, guild_id, summary }` — fed by a tiny
append-only `events` table the bot writes to (command used,
member joined, bot restarted, admin action taken) and the API
reads. The recent-events table on the one-screen layout polls
this endpoint on its own 30–60 s interval; it is the live
update the reader actually watches. Treat it as the audit log
too: every admin action from the command bridge writes one row
here (who, what, when) before it replies success, and a toast
claims success only after that row exists. For the live upgrade,
this is the channel to push: subscribe to `events + INSERT`,
broadcast the new row over SSE or WebSocket, and keep polling
as the fallback transport — same channel, same JSON, different
wire. Do not invent a second event shape for the socket later.
Live updates come from this revision feed, not from re-reading
whole tables, and per-role permissions are enforced in the API
layer on every query, not in the frontend.
