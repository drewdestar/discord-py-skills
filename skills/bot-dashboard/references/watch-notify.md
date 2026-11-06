## Watch / notify: the dashboard that taps you on the shoulder

A dashboard that only displays is half a dashboard. The other
half watches numbers and tells a human when one goes wrong. A
watch is one record: `{ target, interval, selector/filter,
trigger condition, notification channels }`. Map it directly
onto bot health:

| Watch | Target | Trigger |
|---|---|---|
| Guild count | `GET /api/stats` guilds | Drops by more than 1 in an hour |
| Gateway latency | bot heartbeat | Above 500 ms for 5 minutes |
| Command error rate | events, `type = "command_error"` | Above 5% of commands in 10 minutes |
| Restart count | events, `type = "bot_restarted"` | More than 2 in an hour |

Each watch has its own interval (the per-widget table in `references/realtime-polling.md` is
the starting point), its own threshold, and its own channels —
a Discord webhook in the staff channel, a DM to the owner, or
both. There is one `notify()` helper, not a sender per channel:
`notify(watch, message)` fans out to every channel the watch
lists, and the watch does not know or care how many there are.
Add trend graphs for the two numbers that move: error rate and
latency over time, on the one-screen layout under the chart, so
a spike is visible before the notification arrives. A watch can
also carry a timezone and a day-window ("weekdays 08:00–22:00
WIB only") so a 3 a.m. restart during a planned deploy does not
wake anyone. Watches live in the dashboard's own config, not in
the bot's economy tables, and a fired watch writes one row to
the events feed — so the notification and the audit trail are
the same fact.
