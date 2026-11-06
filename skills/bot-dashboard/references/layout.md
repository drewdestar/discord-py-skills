## Layout: the one-screen dashboard

Build exactly this screen, in this order — it is the composition
pi-hole, the Nuxt dashboard template, AdminLTE, and Tabler all
converge on, so do not invent a different one:

1. A top row of 4 stat cards, AdminLTE "small box" style: one big
   number, one label, one small delta against the previous period,
   and an icon. Suggested cards: Guilds, Members, Commands today,
   Uptime. Colour the delta by direction, not by sentiment.
2. One chart card below it: a Chart.js line/area chart of commands
   over time, fed by polling `/api/stats`. Replace the demo's
   hand-drawn bars with this chart when you leave the demo.
   (ApexCharts is an acceptable alternative — it is not MIT: its
   current licence is free only under $2M annual revenue/budget,
   with a commercial licence above that and premium chart types
   watermarked without a key. Do not call it MIT, and do not
   present it as AdminLTE's default — AdminLTE 4.10's own demos
   use Chart.js.)
3. A recent-events / top-N table beside or below the chart: top
   commands today, then the newest events (see "Revision / audit
   feed"). Paginate at 50 rows per page, with search. The top-N
   table reads pre-computed summary tables refreshed on a
   schedule, not a `SELECT … GROUP BY` over the whole ledger on
   every poll; live updates come from the revision feed, not from
   re-reading whole tables.

Build it with plain HTML + CDN CSS/JS + `fetch()` polling — one
AdminLTE or Tabler CSS file and one Chart.js script tag, no
framework, no build step, no Node. Take the small-box cards and
the shell from AdminLTE and ignore the other 95% (Kanban, mailbox,
18 demo pages). A framework earns nothing here and costs a build
step the reader did not ask for.

- Empty states say what happened and what to do next ("No
  commands yet today — try /ping in your server"). An empty state
  that reads as a page that failed to load is a bug, not a state.
- A loading state never wears the disabled dimming. If it looks
  like the user cannot do something, they will believe it.
- A toast claims success only after the list it describes
  actually changed. A toast that lies is worse than silence.
- Destructive actions use the danger color, never the primary
  color. A "Delete" button in primary blue is a misclick waiting
  to happen. This is a measured rule (token-by-intent), not taste.
