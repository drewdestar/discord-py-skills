#!/usr/bin/env python3
"""Apply numbered SQLite migrations, in order, before the bot starts.

Usage:
    python3 scripts/migrate.py --db data/bot.db --migrations migrations/

Contract (see skills/economy-database/SKILL.md, "Migrations"):
- Migrations are numbered files (NNN_descriptive_name.sql) in the
  --migrations directory. They are applied in number order, one
  transaction per migration, and each one is recorded in the
  schema_migrations table in the same transaction. If any migration
  fails, it stops, rolls that migration back, and applies nothing
  further.
- Run this while the bot is STOPPED, before starting it. Never from
  bot code, never at bot startup.
- Before touching the live database, a shadow-DB drift check runs:
  the live file is copied, the pending migrations are replayed into
  the copy, and the result is diffed against a fresh database built
  from all migrations. Any difference means someone hand-edited the
  live database: migration is refused. The diff compares sqlite_master
  SQL text plus PRAGMA table_info per table, excluding sqlite_sequence
  contents (row values are data, not schema).
- A lock file (<db>.lock) refuses to run while a backup is in
  progress, and the backup job checks the same file. If a previous
  run crashed, delete the lock file by hand after confirming no
  backup or migration is running.

Migration files must contain only the up statements (DDL/DML). Do not
put transaction control (BEGIN/COMMIT) in them; the runner owns the
transaction. A down (rollback) lives as a commented block at the end
of the file; it is documentation, not something this script runs.

Standard library only.
"""

import argparse
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

MIGRATION_RE = re.compile(r"^(\d{3})_(.+)\.sql$")
TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def fail(message: str) -> "SystemExit":
    print(f"migrate: error: {message}", file=sys.stderr)
    return SystemExit(1)


def list_migrations(migrations_dir: Path) -> list:
    """Numbered migration files, sorted, with gap detection."""
    found = []
    for path in sorted(migrations_dir.iterdir()):
        match = MIGRATION_RE.match(path.name)
        if match and path.is_file():
            found.append((match.group(1), match.group(2), path))
    if not found:
        raise ValueError(f"no migration files in {migrations_dir}")
    numbers = [int(version) for version, _, _ in found]
    if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        raise ValueError(
            f"gap in migration numbering in {migrations_dir}: "
            f"found {numbers}; find the missing file before applying anything")
    return found


def ensure_tracking(conn: sqlite3.Connection) -> None:
    conn.execute(TRACKING_TABLE)


def applied_versions(conn: sqlite3.Connection) -> set:
    ensure_tracking(conn)
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}


def read_migration(path: Path) -> str:
    # pathlib, never a cwd-relative open(): the migrations dir comes
    # from --migrations, so this works from any working directory.
    return path.read_text(encoding="utf-8")


def _is_only_comments(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return False
    return True


def execute_script(conn: sqlite3.Connection, sql: str) -> None:
    """Run multi-statement SQL inside the caller's transaction.

    executescript() cannot be used here: it commits any pending
    transaction first, which would split the migration from its
    tracking row. Split on complete statements (sqlite3's own parser)
    and execute them one by one instead.
    """
    buf = ""
    for line in sql.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                conn.execute(buf)
            buf = ""
    if buf.strip() and not _is_only_comments(buf):
        raise ValueError("migration ends with an incomplete statement")


def apply_one(conn: sqlite3.Connection, version: str, name: str, sql: str) -> None:
    """One migration + its tracking row, in one transaction."""
    conn.execute("BEGIN")
    try:
        ensure_tracking(conn)
        execute_script(conn, sql)
        conn.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
            (version, name),
        )
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass  # nothing to roll back; the original error is the report
        raise


def apply_pending(conn: sqlite3.Connection, migrations: list) -> list:
    """Apply every migration not yet recorded. Returns applied versions."""
    applied = applied_versions(conn)
    done = []
    for version, name, path in migrations:
        if version in applied:
            continue
        apply_one(conn, version, name, read_migration(path))
        done.append(version)
        print(f"applied {version}_{name}")
    return done


def schema_signature(conn: sqlite3.Connection) -> list:
    """sqlite_master SQL text + PRAGMA table_info per table, excluding
    sqlite_sequence (its row values are AUTOINCREMENT counters: data,
    not schema)."""
    sig = []
    for row in conn.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ):
        sig.append(("master", row[0], row[1], row[2]))
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for table in tables:
        cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        sig.append((
            "table_info",
            table,
            tuple((c[1], c[2], c[3], c[4], c[5]) for c in cols),
        ))
    return sig


def drift_check(db_path: Path, migrations: list) -> None:
    """Shadow-DB check: live + pending must equal fresh + all."""
    with tempfile.TemporaryDirectory(prefix="migrate-shadow-") as tmp:
        tmp = Path(tmp)
        shadow_path = tmp / "shadow.db"
        shutil.copyfile(db_path, shadow_path)
        fresh_path = tmp / "fresh.db"
        shadow = sqlite3.connect(shadow_path, isolation_level=None)
        fresh = sqlite3.connect(fresh_path, isolation_level=None)
        try:
            apply_pending(shadow, migrations)
            # Fresh gets every migration, not just the pending ones.
            for version, name, path in migrations:
                apply_one(fresh, version, name, read_migration(path))
            if schema_signature(shadow) != schema_signature(fresh):
                raise ValueError(
                    "drift detected: the live database does not match the "
                    "migrations. Someone hand-edited it. Refusing to "
                    "migrate; compare the shadow copy against a fresh "
                    "database built from migrations/ and fix the live "
                    "database by hand first (or restore from backup).")
        finally:
            shadow.close()
            fresh.close()


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply numbered SQLite migrations before the bot starts.")
    parser.add_argument("--db", required=True, help="database file, e.g. data/bot.db")
    parser.add_argument("--migrations", required=True,
                        help="directory of NNN_name.sql files")
    args = parser.parse_args(argv)
    db_path = Path(args.db)
    migrations_dir = Path(args.migrations)
    if not migrations_dir.is_dir():
        print(f"migrate: error: no such directory: {migrations_dir}", file=sys.stderr)
        return 1
    try:
        migrations = list_migrations(migrations_dir)
    except ValueError as exc:
        print(f"migrate: error: {exc}", file=sys.stderr)
        return 1

    lock_path = db_path.with_name(db_path.name + ".lock")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(f"migrate: error: lock file exists: {lock_path} — a backup or "
              "another migration is running (or a previous run crashed; "
              "delete it by hand after confirming nothing is running).",
              file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"migrate: error: cannot create lock file {lock_path}: {exc}",
              file=sys.stderr)
        return 1
    try:
        fresh_db = not db_path.is_file()
        if not fresh_db:
            try:
                drift_check(db_path, migrations)
            except ValueError as exc:
                print(f"migrate: error: {exc}", file=sys.stderr)
                return 1
        conn = sqlite3.connect(db_path, isolation_level=None)
        try:
            done = apply_pending(conn, migrations)
        finally:
            conn.close()
        if done:
            print(f"migrated {db_path} to {done[-1]} ({len(done)} applied)")
        else:
            print(f"{db_path} is up to date")
        return 0
    except sqlite3.Error as exc:
        print(f"migrate: error: {exc}", file=sys.stderr)
        return 1
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
