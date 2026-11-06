## Backups

A backup is a snapshot, not a file copy. Never copy a live database file. A plain `cp` of `data/bot.db` while the bot is running can capture the main file and the `-wal` file at different moments, and the result is a corrupt backup that looks fine until restore day. Follow this sequence, in this order, every hour:

### The sequence

1. **Checkpoint the WAL.** Fold the write-ahead log into the main file and truncate it, so the snapshot that follows is complete:

   ```sql
   PRAGMA wal_checkpoint(TRUNCATE);
   ```

   Do this on the bot's own connection, or on a connection that can wait for the writer to finish — never by deleting the `-wal` file. Deleting the `-wal` file deletes committed transactions. `TRUNCATE` ensures the checkpoint runs to completion; while it runs, readers might block briefly. `PASSIVE` never blocks, but it may not complete under constant readers, so the hourly job uses `TRUNCATE`. The checkpoint is good practice, not a correctness requirement: the backup API below yields a consistent copy on a live database with or without it. It folds the WAL into the main file, which shrinks and speeds the copy. (Pattern borrowed from DuckDB's explicit `CHECKPOINT` before backup and MongoDB's journal + checkpoint discipline — patterns only.)

2. **Snapshot with SQLite's backup API.** Copy the database through the engine, not through the filesystem, while the bot keeps running:

   ```python
   import aiosqlite

   async def snapshot(db: aiosqlite.Connection, dst_path: str) -> None:
       """Consistent snapshot of a live database. The bot keeps running;
       the copy is taken through the backup API, page by page, so it can
       never catch the file mid-write."""
       dst = await aiosqlite.connect(dst_path)
       try:
           await db.backup(dst)   # aiosqlite backup API: online, consistent
       finally:
           await dst.close()
   ```

   The standard-library equivalent is `sqlite3.Connection.backup()` on a separate read-only connection. `VACUUM INTO 'backup.db'` is the acceptable alternative (SQLite 3.27 or later, after a commit). Pick one and use it everywhere; do not mix methods between runs, or two backups from the same hour will not be comparable.

3. **Verify the copy before you trust it.** A backup that was never opened is a hope, not a backup. Immediately after step 2, on the copy only — never on the live file:

   ```python
   import sqlite3

   def verify_backup(backup_path: str, live_counts: dict) -> None:
       """Open the snapshot read-only, check integrity, and spot-check
       row counts against the live counts taken before the snapshot.
       Raise on any mismatch."""
       chk = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
       try:
           result = chk.execute("PRAGMA integrity_check").fetchone()[0]
           assert result == "ok", f"integrity_check failed: {result}"
           for table in ("users", "transactions", "schema_migrations"):
               n_backup = chk.execute(
                   f"SELECT COUNT(*) FROM {table}").fetchone()[0]
               assert n_backup == live_counts[table], (
                   f"{table}: backup has {n_backup}, live has {live_counts[table]}")
       finally:
           chk.close()
   ```

   - `PRAGMA integrity_check` must return exactly `ok`. Anything else means the snapshot is corrupt: delete it, alert, and take another one. Do not keep a corrupt backup "just in case".
   - Take the live counts on the bot's connection before the snapshot (`SELECT COUNT(*)` per table) and pass them in. A mismatch means the snapshot caught the database mid-write — which the backup API should prevent — so treat it as a failure of the backup job, not as noise to ignore. (The table names in the check must be hard-coded, never built from user input; the f-string above interpolates fixed table names from the skill's own list, not user data.)
   - Verification runs on every backup, automatically. A weekly "test restore" is in addition to this, not instead of it: once a week, restore one hourly snapshot into a scratch copy and read a known balance from it, as the skill's "Verify live" section already requires.

4. **Write a separate portable dump as a second artifact.** The snapshot is for disaster recovery (fast restore, same SQLite version). The dump is for migration and inspection (portable, human-readable, cross-version). They are two different jobs — do not conflate them (pattern borrowed from Meilisearch's snapshot-vs-dump split — Apache-2.0 core / BUSL-1.1 Enterprise; pattern only, no code copied):

   ```bash
   # Portable logical export, alongside the binary snapshot.
   sqlite3 data/bot.db .dump | gzip > backups/bot-2026-11-06T12-00.sql.gz
   ```

   The dump is SQL text: it can be read, grepped, and restored into a newer SQLite version. The snapshot cannot do any of those. Keep both artifacts for every backup run, with matching timestamps in the filename so a snapshot and its dump can always be paired.

5. **Retain, then delete.** Keep 7 days of hourly snapshots and dumps, then delete older ones. Retention is a first-class setting, not an afterthought: name it in the backup script's config (`RETENTION_DAYS = 7`), and delete whole expired backup sets — snapshot plus its dump together — never one without the other. A snapshot without its dump is half a backup set. Prune with one command, for example: `find backups/ -name 'bot-*' -mtime +7 -delete`. On Windows, a live `.db` file cannot be copied while the bot holds it open — use the backup API above, never Explorer or copy.

### Rules that stay

- Never ship the `.db` file in git. It belongs in `.gitignore` and in the backup directory only. Backups belong in the backup directory only, too — never in the repository, never in a public folder.
- Name the durability window honestly. `synchronous=NORMAL` (the connection setup in this skill) means a committed write can be lost if the operating system crashes before the WAL is flushed — the same trade-off as Redis's `everysec` appendfsync policy (Redis is RSALv2 / SSPLv1 / AGPLv3 since v8; pattern only, no code copied). If a transfer must survive a power cut, use `synchronous=FULL` for economy writes and never report success before `commit()` returns. Do not pretend writes are instantly safe.
- A backup taken while a migration is running is not a backup. The backup job must refuse to run while `scripts/migrate.py` is running, and migrations must refuse to run while a backup is in progress. One lock file, checked by both.
