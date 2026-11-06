## The dashboard reads. It never writes.

The dashboard is a reader of the economy, never a writer. All writes go through the bot's economy module only. No exceptions, no "just this once", no admin button that writes straight to the database.

- **The dashboard connects read-only.** Open the economy file with a read-only connection, and say so in the connection string so a future edit cannot accidentally turn it into a writer:

  ```python
  import aiosqlite

  # Dashboard side only. mode=ro refuses to open the file for
  # writing, and query_only is a second lock on the same door.
  dash_db = await aiosqlite.connect(f"file:{DB_PATH}?mode=ro", uri=True)
  await dash_db.execute("PRAGMA query_only = ON")
  ```

  The same URI works with the standard library: `sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)`. A separate read connection is the whole point: SQLite in WAL mode lets readers run concurrently with the bot's writer without blocking it — but only if the reader never takes a write lock. A dashboard connection that can write will, one day, write.
- **The dashboard never writes economy tables.** No `UPDATE users`, no `INSERT INTO transactions`, no "fix this balance" endpoint, no direct SQL from the dashboard process at all. If the dashboard needs to change something — a refund, a manual grant, a correction — it calls the bot's own API or command, and the bot's economy module performs the write, with its lock, its transaction, its CAS guard, its ledger row, and its revision bump. There is exactly one writer, and it lives in the bot.
- **The dashboard's own state lives elsewhere.** Sessions, OAuth tokens, dashboard settings, and cached stats are the dashboard's metadata, not the economy's. Keep them in a separate file (or a separate table the bot never touches) — never mix dashboard state into the economy database. (Pattern borrowed from Metabase's two-database split — AGPL-3.0, pattern only: the application database holds metadata, the business data lives in the connected database.)
- **Reads must be cheap and scoped.** The dashboard polls the revision feed from the previous section (`WHERE id > ?`) for live updates instead of re-reading whole tables, and it serves leaderboards from pre-computed summary tables refreshed on a schedule instead of running `SELECT … GROUP BY` over the whole ledger on every page load. A dashboard that full-scans the ledger on every poll is a denial-of-service attack the bot inflicts on itself. Enforce per-Discord-user scoping in the API layer on every query — a regular user sees only their own row — and never rely on the frontend hiding buttons. (Patterns borrowed from ClickHouse's pre-aggregation and Metabase's group permissions / Supabase's row-level security — Apache-2.0 projects, patterns only.)
- **SQLite has no shared-writer mode.** H2's `AUTO_SERVER` mixed mode lets an embedded process own the file while a second process connects over TCP (H2, MPL-2.0 / EPL-1.0 — pattern only). SQLite cannot do this. Do not look for the SQLite equivalent: there is not one. The SQLite-safe equivalent is routing all dashboard access through the bot's own API, or through a read-only connection as above — never a second direct writer.
