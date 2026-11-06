## Realtime: per-widget polling intervals

Do not use one global timer. Every widget has its own refresh
interval, the Dashy pattern: fast numbers refresh fast, slow
numbers refresh slow. (Dashy is the actively maintained
dashboard that documents per-widget refresh; the older
danielbayerlein dashboard it replaces has been stalled since
2023.) Start from this table and adjust only with a reason:

| Widget | Interval | Why |
|---|---|---|
| Bot status / uptime | 10 s | Fast-changing, cheap to read |
| Commands today, chart | 10 s | The headline number; stale is visible |
| Guild / member totals | 60 s | Slow-changing; re-reading them every 10 s buys nothing |
| Top commands, events table | 30–60 s | Aggregates; nobody watches them tick |

Give each widget its own `setInterval(fetch…)` (or one small
`poll(widget, ms)` helper) and one named constant per interval at
the top of the script, so the interval is visible and changeable,
never hard-coded and invisible. Fetch-on-load-only is the Glance
anti-pattern: if you only fetch on load, your member count goes
stale — add polling. WebSocket and SSE are upgrade paths, not the
starting point: a dashboard that polls every 10 seconds and shows
fresh numbers is a working dashboard; a dashboard with a
half-built socket layer is a broken one.

When you do upgrade to SSE, treat it as streamed, progressive
updates — not a faster poll. Push partial updates as they arrive
(a new event row, a changed counter) and patch the page in
place, instead of re-fetching everything and repainting the
whole screen. The UI must show stale and loading states
explicitly while it waits: a widget that has not heard from the
server says so ("updated 42 s ago"), and a widget still loading
says that too, instead of silently showing yesterday's number
as if it were live. Polling stays the default; SSE is the
upgrade, and the transport seam (`Realtime transport: one seam, swappable transports`, in SKILL.md) is what makes that upgrade
cheap.
