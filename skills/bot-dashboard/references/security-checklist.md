## Security checklist (before the dashboard leaves localhost)

- [ ] Discord OAuth2 login implemented: code flow, `state`
  checked, client secret server-side only, staff role gate.
- [ ] Bot token is not in the web process, the browser, the
  logs, or the repo. Ever.
- [ ] API responses are rate-limited; admin actions are written
  to an audit log (who, what, when).
- [ ] HTTPS in production, with HSTS. No dashboard without it.
- [ ] `/health` returns 200 only when the database answers (the
  demo checks the database only; a bot-connected variant belongs
  to the FastAPI path — see "Health, per source" in `references/demo-server.md`).
- [ ] The page shows no user data to a user who did not earn it
  (guild membership + role, checked server-side on every
  request, not once at login).
- [ ] User-facing strings go through the `i18n` skill's locale
  tables. A dashboard that hardcodes English fails the
  all-languages bar.
- [ ] One auth middleware guards every `/api` and admin route;
  no handler does its own auth, and no route is unguarded by
  accident. Check by listing routes, not by remembering them.
- [ ] Every dashboard action is a named, validated command;
  there is no generic SQL, eval, or "call any bot method"
  endpoint, and every mutating route checks `canAccess()` again.
- [ ] The session token carries `guild_ids` + `roles`, verified
  on every REST call and every live (SSE/WebSocket) connection,
  not just at login.
- [ ] WebSocket/SSE connections authenticate before `accept()`
  (cookie or short-lived ticket — never an `Authorization`
  header the browser cannot send); see "WebSocket auth gotcha".
- [ ] The dashboard binds `127.0.0.1` until HTTPS + OAuth2 +
  the role gate are all live; reaching it from the internet
  needs a tunnel (frp is the self-hosted option) plus those
  three, not just one of them.
- [ ] No AGPL/GPL code was vendored or copied into the pack;
  patterns only (see "Licence safety").
