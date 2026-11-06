## Auth: Discord OAuth2, done the boring way

Login is Discord OAuth2, authorization-code flow. The boring way
is the secure way:

1. The user clicks login and is sent to Discord with `client_id`,
   `redirect_uri`, `response_type=code`, `scope=identify guilds`,
   and a random `state` value stored server-side (in a signed,
   httpOnly, Secure, SameSite cookie or server session).
2. Discord redirects back with a code. The server checks the
   `state` matches what it stored. A mismatch is a rejected
   login, always — that check is the CSRF protection.
3. The server exchanges the code for tokens with the client
   secret, server-side only. The client secret never reaches the
   browser, and neither does any token.
4. The server calls Discord with the access token to get the user
   (`identify`) and their guilds (`guilds`). It admits the user
   only if they are a member of the bot's guild AND hold a staff
   role. Everyone else gets a plain "not authorized" page — never
   a leak of what exists behind the gate.
5. Sessions live server-side. Refresh tokens live server-side.
   The browser holds one opaque session cookie and nothing else.

Scopes to ask for: `identify` and `guilds`. Do not ask for
`email` unless the dashboard genuinely needs it, and do not ask
for anything that lets the dashboard act as the user. The
authorization-code grant is the only flow to use; the implicit
flow is not acceptable.

Keep the Discord OAuth2 code flow above — it does not change.
What changes is where the check lives. Write exactly one auth
middleware and put it on every `/api` and admin route; do not
sprinkle auth logic through handlers. The middleware resolves
the Discord OAuth2 user from the session, checks guild
membership AND staff role, stores the verified user (id,
`guild_ids`, `roles`) in the request context, and aborts the
chain on failure — no handler ever runs for an unauthorised
caller, and no handler ever re-checks what the middleware
already proved. The session token carries `guild_ids` + `roles`,
and the server verifies them on *every* REST call and on *every*
live connection, not just at login: a role revoked after login
must stop working on the next call, not at the next login.
Every action the browser can trigger is a named, validated
command — `run_command`, `restart_bot`, `ban_member` — with its
payload validated server-side against a Pydantic model and its
permission checked with one `canAccess({ resource, action })`
call ("has Moderator role" ⇔ `canAccess({ resource: "settings",
action: "edit" })`). There is no generic "run this SQL" or "call
this bot method" endpoint. A write endpoint that only the
frontend hides is an open endpoint: check permission on every
mutating route, every time.

This pattern is what the real dashboards do: the FastAPI +
Disnake + Vite React + Supabase panel gates its control panel to
staff roles via Discord OAuth2, and the FastAPI + WebSocket
example in the research gates play behind guild membership and
role verification with state. The demo server in this
skill does NOT implement OAuth2 — implementing login is the
first real task when the dashboard leaves localhost, and the
checklist at the end of this skill does not let you forget it.

### WebSocket auth gotcha

FastAPI's security classes cannot be used directly as WebSocket
dependencies — they expect a `Request`, and a WebSocket
handshake has none to give them. Worse, a browser cannot send
an `Authorization` header on the WebSocket handshake at all:
the browser `WebSocket` constructor takes only a URL and an
optional subprotocol list, so there is no slot for a header.
(Non-browser clients can send headers; this is a browser-client
gotcha, not a FastAPI limitation.) Authenticate the socket
before `accept()`: read the session from a cookie, or accept a
short-lived ticket issued over an already-authenticated REST
call and passed as a query parameter — FastAPI's own WebSocket
tutorial demonstrates exactly this, a dependency reading either
a `Cookie()` session or a `Query()` token and rejecting with
`WS_1008` when both are missing — verify `guild_ids` +
`roles` exactly as the REST middleware does, and raise
`WebSocketException` (not `HTTPException`) on failure. Two
other accepted patterns: the token in the
`Sec-WebSocket-Protocol` subprotocol value, and first-message
auth with a short deadline. Never `accept()` first and check
later — an accepted socket is an open door. And never put a
long-lived token in the query string: URLs land in logs and
browser history, so the ticket must be short-lived and
single-use; the cookie path needs `SameSite`/CSRF attention
cross-origin.
