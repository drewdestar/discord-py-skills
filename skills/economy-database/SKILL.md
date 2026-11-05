---
name: economy-database
description: "Build a safe SQLite economy for a discord.py bot: WAL mode, schema with migrations, atomic transactions, idempotency keys, and hourly backups. Use when adding currency, inventories, shops, or any persistent player data."
---

# Economy Database

A bot economy is a ledger, not a number in a column. This skill builds the SQLite layer that keeps balances correct when two commands run at the same time, when the process restarts mid-trade, and when a user retries a slow request.

## Rules first

1. **One writer.** SQLite allows one writer at a time. All writes go through one connection (or one lock) so two commands never interleave a balance update.
2. **Ledger as source of truth.** Every balance change is a row in a transactions table. The balance column is a cache of the ledger sum. If the two ever disagree, the ledger wins.
3. **Atomic transfers.** A transfer moves money in a single transaction: check, debit, credit, ledger rows, commit. If any step fails, everything rolls back.
4. **Idempotency keys.** Every credit that comes from outside (daily claim, purchase, reward) carries a unique key. Replaying the same key credits nothing the second time.
5. **Parameterized queries, always.** Never build SQL with f-strings or string concatenation. User input in SQL is an injection bug.

## Schema

See `references/schema.sql` for the full schema. The core tables:

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      INTEGER NOT NULL,          -- positive for credit, negative for debit
    kind        TEXT NOT NULL,             -- 'daily', 'purchase', 'transfer', 'reward'
    idem_key    TEXT UNIQUE,               -- NULL for plain transfers, set for credits
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);
```

- `balance >= 0` as a CHECK constraint: the database itself refuses to create negative money, even if application code has a bug.
- `idem_key` is UNIQUE: the database enforces idempotency, not just the code.
- `kind` makes every row explainable. "Where did this gold come from?" is answerable from the ledger alone.

## Connection setup

```python
import aiosqlite

async def connect(path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(path)
    await db.execute("PRAGMA journal_mode=WAL")   # readers do not block the writer
    await db.execute("PRAGMA busy_timeout=5000")  # wait 5s instead of failing at once
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA synchronous=NORMAL")
    return db
```

- WAL mode is the single most important setting. Without it, a read blocks a write and a write blocks every read, which is how bots freeze under load.
- `busy_timeout` turns a collision into a short wait instead of an immediate error.
- Keep one long-lived connection per bot process and guard writes with an `asyncio.Lock`. Opening a connection per command is slow and invites interleaving.

## Atomic transfer

```python
async def transfer(db, lock, from_id: int, to_id: int, amount: int) -> None:
    if amount <= 0:
        raise ValueError("amount must be positive")
    async with lock:
        async with db.execute("BEGIN IMMEDIATE"):
            row = await (await db.execute(
                "SELECT balance FROM users WHERE user_id = ?", (from_id,)
            )).fetchone()
            balance = row[0] if row else 0
            if balance < amount:
                raise ValueError("insufficient funds")
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (amount, from_id),
            )
            await db.execute(
                "INSERT INTO users (user_id, balance) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
                (to_id, amount, amount),
            )
            await db.execute(
                "INSERT INTO transactions (user_id, amount, kind) VALUES (?, ?, 'transfer')",
                (from_id, -amount),
            )
            await db.execute(
                "INSERT INTO transactions (user_id, amount, kind) VALUES (?, ?, 'transfer')",
                (to_id, amount),
            )
            await db.commit()
```

- `BEGIN IMMEDIATE` takes the write lock up front. Without it, two concurrent transfers can both read the old balance and both succeed, creating money.
- The balance check and the update happen inside the same transaction. A check outside the transaction is a race condition, not a check.
- Any exception before `commit()` rolls the whole transfer back. The ledger never shows half a transfer.

## Idempotent credit

```python
async def credit_once(db, lock, user_id: int, amount: int, kind: str, idem_key: str) -> bool:
    """Credit amount once. Returns True if credited, False if the key was already used."""
    async with lock:
        try:
            async with db.execute("BEGIN IMMEDIATE"):
                # User row first: the transactions table has a foreign key
                # on user_id, so the user must exist before the ledger row.
                await db.execute(
                    "INSERT INTO users (user_id, balance) VALUES (?, ?) "
                    "ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
                    (user_id, amount, amount),
                )
                await db.execute(
                    "INSERT INTO transactions (user_id, amount, kind, idem_key) "
                    "VALUES (?, ?, ?, ?)",
                    (user_id, amount, kind, idem_key),
                )
                await db.commit()
            return True
        except aiosqlite.IntegrityError:
            await db.rollback()
            return False
```

- The daily claim key is `daily:<user_id>:<YYYY-MM-DD>`. Retrying the same day returns False, so a double-click or a retried request never pays twice.
- The UNIQUE constraint on `idem_key` is what makes this safe under concurrency. Application-level "check then insert" is not safe; two requests can both check, both see nothing, and both insert.

## Migrations

```python
async def migrate(db) -> None:
    version = (await (await db.execute("PRAGMA user_version")).fetchone())[0]
    if version < 1:
        await db.executescript(open("migrations/001_init.sql").read())
        await db.execute("PRAGMA user_version = 1")
    if version < 2:
        await db.executescript(open("migrations/002_add_idem_key.sql").read())
        await db.execute("PRAGMA user_version = 2")
    await db.commit()
```

- Schema changes are numbered migration files, applied in order, tracked by `PRAGMA user_version`. Never edit a live database by hand and never `DROP TABLE` in a migration that runs on user data.

## Backups

- Copy the `.db` file once an hour (a running copy with `sqlite3 .backup` or a plain file copy while using WAL with a checkpoint first). Keep 7 days of hourly copies, then delete older ones.
- Test restores. A backup that was never restored is a hope, not a backup.
- Never ship the `.db` file in git. It belongs in `.gitignore` and in the backup directory only.

## Checklist

- [ ] WAL mode on, `busy_timeout` set, foreign keys on
- [ ] One writer: one connection plus one lock
- [ ] Every balance change writes a ledger row
- [ ] Transfers use `BEGIN IMMEDIATE` and check-then-update inside the transaction
- [ ] Every external credit carries a unique idempotency key
- [ ] All queries parameterized, no f-strings in SQL
- [ ] `balance >= 0` enforced by a CHECK constraint
- [ ] Hourly backups exist and one restore was tested
- [ ] `.db` files are in `.gitignore`
