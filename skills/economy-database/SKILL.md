---
name: economy-database
description: "Build a safe SQLite economy for a discord.py bot: WAL mode, schema with migrations, atomic transactions, idempotency keys, and hourly backups. Use when the user says 'add currency', 'my balances reset on restart', or 'two users bought at once and gold duplicated'. Do NOT use for in-memory or JSON storage, and do NOT use SQLite for production on hosts that wipe local files; use Postgres with asyncpg there."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, aiosqlite, no paid services"
metadata:
  version: "0.5.0"
  author: "drewdestar"
---

# Economy Database

A bot economy is a ledger, not a number in a column. This skill builds the SQLite layer that keeps balances correct when two commands run at the same time, when the process restarts mid-trade, and when a user retries a slow request.

> **Sources and license.** The patterns in this skill were learned from real database projects — etcd (Apache-2.0), Prisma (Apache-2.0), Laravel (MIT), Supabase (Apache-2.0), DuckDB (MIT), Prometheus (Apache-2.0), ClickHouse (Apache-2.0), H2 (MPL-2.0 / EPL-1.0) — and are described here in the skill's own words. Patterns only: no code is copied from any of those projects, and none of them is vendored or recommended as a dependency of a bot. In particular, never copy code from, vendor, or recommend as a dependency: MongoDB (SSPL-1.0, source-available, not OSI-approved), Redis (tri-license RSALv2 / SSPLv1 / AGPLv3 since v8), Metabase (AGPL-3.0, OSS edition), Blazegraph (GPL-2.0, archived and dead), or RocksDB's GPL-2.0 licensing limb (dual GPL-2.0 / Apache-2.0). Learning a pattern from one of these projects is fine; copying its code into the pack is not. etcd's compare-and-swap and revision-counter patterns are Apache-2.0, so describing them here is fine — the same "patterns, not code" rule still applies.

## Rules first

1. **One writer.** SQLite allows one writer at a time. All writes go through one connection (or one lock) so two commands never interleave a balance update.
2. **Ledger as source of truth.** Every balance change is a row in a transactions table. The balance column is a cache of the ledger sum. If the two ever disagree, the ledger wins. Prove it with a reconciliation query, not a feeling:

   ```sql
   -- Every user's ledger sum must equal their balance column.
   SELECT user_id, SUM(amount) AS ledger_sum FROM transactions GROUP BY user_id;
   ```

   Compare each `ledger_sum` against `users.balance`. A mismatch means a write moved money without a ledger row (or the reverse) — find that write, do not adjust the numbers to match.
3. **Atomic transfers.** A transfer moves money in a single transaction: check, debit, credit, ledger rows, commit. If any step fails, everything rolls back.
4. **Idempotency keys.** Every credit that comes from outside (daily claim, purchase, reward) carries a unique key. Replaying the same key credits nothing the second time.
5. **Parameterized queries, always.** Never build SQL with f-strings or string concatenation. User input in SQL is an injection bug.
6. **Every mutation bumps a revision.** A balance change without a ledger row and a version bump did not happen — roll it back.
7. **The dashboard reads; it never writes.** All writes go through the bot's economy module. A dashboard write is a bug, not a feature.

## Schema

The schema: users, ledger, idempotency keys, and the version column. See `references/schema.md`.

## Every mutation bumps a revision

Every mutation bumps a revision: the global sequence, per-user version, and compensating rows. See `references/revision-feed.md`.

## Connection setup

Connection setup: WAL mode, the PRAGMA check, and `synchronous`. See `references/connection-setup.md`.

## Atomic transfer (compare-and-swap)

The atomic transfer (compare-and-swap): one transaction, one version bump, no double-spend. See `references/transfer.md`.

## Idempotent credit

Idempotent credit: `credit_once` and the daily claim. See `references/idempotent-credit.md`.

## Wiring /daily to Discord

`credit_once` returns a boolean; the command turns it into the words the user sees. That mapping is the whole command:

```python
from datetime import datetime, timezone

@app_commands.command(name="daily", description="Claim your daily gold.")
async def daily(interaction: discord.Interaction):
    key = f"daily:{interaction.user.id}:{datetime.now(timezone.utc).date().isoformat()}"
    paid = await credit_once(interaction.client.db, interaction.client.db_lock,
                             interaction.user.id, 100, "daily", key)
    text = "You claimed 100 gold." if paid else "You already claimed today."
    await interaction.response.send_message(text, ephemeral=True)
```

- The boolean is the behaviour: `True` means "You claimed 100 gold", `False` means "already claimed". Do not re-check the balance to decide the words; the return value already knows.
- `db` and `db_lock` live on the bot object (see the starter bot's `bot.py`: the bot owns one connection and one lock). The command never opens its own connection.
- The key uses the UTC date (see "Idempotent credit"), so a user cannot claim twice by crossing a timezone boundary.

## Migrations

Migrations discipline: numbered files, one transaction each, the shadow-DB drift check, and `scripts/migrate.py`. See `references/migrations.md`.

## Backups

Backups: checkpoint, the backup API, verification, the portable dump, and retention. See `references/backups.md`.

## The dashboard reads. It never writes.

The dashboard reads. It never writes: read-only mode, `query_only`, and cheap scoped reads. See `references/dashboard-reads.md`.

## Race test: two claims at once must not double-pay

The race test: two claims at once must not double-pay. See `references/race-test.md`.

## Persistence warning

SQLite is a file. On hosts that wipe local files on redeploy (Railway, Heroku, and similar), the database disappears with the deploy and every balance resets to zero. For production on such a host, use Postgres with `asyncpg` instead, keeping the same rules: one writer, ledger as source of truth, atomic transfers, idempotency keys, parameterized queries.

## Verify live

- Restart the bot. Balances are exactly what they were before.
- Run `/daily` twice in a row in Discord. The second run says the reward was already claimed; the balance moved once.
- Restore one hourly backup into a scratch copy and read a known balance from it. A backup that was never restored is unproven.

## Quality bar (no slop)

- Never invent a balance, a price, or a count. The ledger is the source of truth; a number shown to a user comes from a query.
- No em dash in any message or embed the bot sends.

## Checklist

- [ ] WAL mode on, `busy_timeout` set, foreign keys on
- [ ] One writer: one connection plus one lock
- [ ] Every balance change writes a ledger row
- [ ] Transfers use `BEGIN IMMEDIATE` + CAS (`UPDATE … WHERE version = ?`) with a `rowcount` check and bounded retry
- [ ] Every external credit carries a unique idempotency key
- [ ] All queries parameterized, no f-strings in SQL
- [ ] `balance >= 0` enforced by a CHECK constraint
- [ ] `synchronous` set deliberately: NORMAL with WAL (can lose recent transactions on power loss), FULL for writes that must survive a power cut
- [ ] Every balance write bumps `users.version` and writes a ledger row; corrections are new rows, never edits
- [ ] Dashboard can poll "what changed since rev N" from the ledger id; a gap triggers a full re-sync
- [ ] Migrations live in numbered files with up/down, tracked in `schema_migrations`, applied explicitly before bot start; a shadow-DB drift check runs first; nothing auto-generates or auto-applies at runtime
- [ ] Dashboard connects read-only (`mode=ro` + `query_only`) and never writes economy tables; all writes go through the bot's economy module
- [ ] Hourly backups exist: checkpoint → backup API → integrity check + row-count spot-check → portable dump, and one restore was tested
- [ ] No code copied from AGPL/SSPL/GPL-licensed repos; patterns only, in the skill's own words
- [ ] `.db` files are in `.gitignore`
