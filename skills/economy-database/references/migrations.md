## Migrations

Migrations are a discipline, not a script. Every schema change is a numbered file, applied in order, recorded in a tracking table, and reversible. Nothing else changes the schema. Ever.

### The tracking table

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,   -- e.g. '001', '002', never reused
    name        TEXT NOT NULL,      -- e.g. '001_init', '002_add_idem_key'
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

`PRAGMA user_version` is not the tracker. A single integer cannot say which migrations applied, when they applied, or whether the live database drifted from the files. Keep `user_version` at 0 and use `schema_migrations` as the only record. (Pattern borrowed from Prisma's `_prisma_migrations` and Supabase's `supabase_migrations.schema_migrations` tables — Apache-2.0 projects; the pattern, not their code.)

### The files

- One migration per change, in `migrations/`, named `NNN_descriptive_name.sql` — `001_init.sql`, `002_add_idem_key.sql`, `003_add_user_version.sql`. Numbers are ordered and never reused. A gap in the numbering is a mistake: find the missing file before you apply anything.
- Every migration has two parts: `up` (the change) and `down` (how to undo it), in the same file or in a paired `NNN_…_down.sql`. A migration without a `down` is not finished. (Pattern borrowed from Laravel's `up()` / `down()` pairs — MIT.) The `down` must be tested, not just written: apply `up`, apply `down`, confirm the schema is back where it started.
- Migrations are additive and backward-compatible while the bot is running. Add a column with a default; do not rename or drop a column the live code still reads. A destructive change (`DROP TABLE`, `DROP COLUMN`) needs a two-release plan: first release stops reading the column, second release drops it.
- Never edit an applied migration. If `002` was wrong, write `004` that fixes it. Editing history means two databases that both claim to be "at version 003" hold different schemas, and no check can tell them apart.
- Never edit a live database by hand. No `sqlite3` one-liners against `data/bot.db`, no dashboard "fix the schema" button. Every schema change goes through a migration file, or it does not happen.
- The reference migrations live in `references/migrations/` in this skill (`001_init`, `002_add_idem_key`, `003_add_user_version`). A bot project copies them into its own `migrations/` and runs `scripts/migrate.py` against them.

### How migrations run

Migrations run explicitly, in order, before the bot starts. They do not run at bot runtime, and they are never auto-generated at runtime.

```bash
# The only way migrations are applied. Run it by hand, or from a
# deploy script, before starting the bot — never from bot code.
python3 scripts/migrate.py --db data/bot.db --migrations migrations/
python3 bot.py
```

- `scripts/migrate.py` reads `schema_migrations`, finds the numbered files that have not applied yet, and applies them in number order, one transaction per migration, recording each one in `schema_migrations` in the same transaction. If any migration fails, it stops, rolls that migration back, and applies nothing further. A half-migrated database is worse than an unmigrated one.
- Migration files are loaded with `pathlib` from the `--migrations` argument and read with `encoding="utf-8"`, never with a cwd-relative `open()`. A migrate that only works from the project root is a latent bug.
- There are two paths, and they never mix (pattern borrowed from Prisma Migrate — Apache-2.0):
  - **Dev** may *generate* a migration from a schema change, for review. Generation writes a file; it never touches a database.
  - **Deploy / production** only *applies* already-reviewed files. It never generates, never edits a file, and never runs a migration that has not been read by a human.
- Do not auto-migrate at bot startup. The research mentions Liquibase-style "migrate automatically at boot" (Metabase, AGPL-3.0 — pattern only, no code copied) as a convenience. Do not take it: a bot that rewrites its own schema on start can corrupt data before anyone is watching, and a failed auto-migration leaves the bot half-started against a half-migrated database. The explicit pre-start step is the whole point.

### Drift check: the shadow database

Before applying anything to the live database, prove the live database matches the migrations. Copy the file to a temporary path, replay every migration into the copy, and diff the result against the intended schema. If they differ, someone hand-edited the live database: refuse to migrate, and say so loudly. Do not silently diverge.

```bash
# What scripts/migrate.py does before touching data/bot.db:
#   1. cp data/bot.db /tmp/shadow.db
#   2. replay the PENDING migrations into /tmp/shadow.db (not all of
#      them: ADD COLUMN is not idempotent, so replaying an applied
#      migration would fail on a duplicate column)
#   3. build a fresh database from ALL migrations, and compare
#      sqlite_master + PRAGMA table_info between the shadow copy and
#      the fresh build; exclude sqlite_sequence contents (row values
#      are data, not schema); any difference = drift = stop.
#   4. only then apply the pending migrations to data/bot.db.
```

- The shadow database is a throwaway copy. Delete it after the check. Never migrate the shadow and then swap it in as the live database — the live file holds the money; the copy holds nothing.
- The drift check runs on every migrate, not just the first one. Drift is usually discovered months later, when it is expensive. Catch it at the moment it appears.

### What "reversible" means in practice

- Adding a column: `down` drops it — only if no live code reads it yet. If live code already reads it, the `down` is "deploy the previous release first, then drop the column".
- Adding a table: `down` drops the table — only if it holds no user data. If it holds user data, the `down` archives the table (`ALTER TABLE … RENAME TO …_archived_YYYYMMDD`) instead of dropping it. Dropping user data to roll back a schema change is destroying the economy to save the schema.
- Never `DROP TABLE` in a migration that runs on user data without an archive step. The current skill already says this; it stays, and it now applies to `down` migrations too.
