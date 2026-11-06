"""SQLite economy layer for the starter bot.

One writer (one connection plus one asyncio.Lock), WAL mode, a ledger
table as the source of truth, and idempotency keys on every credit.
See skills/economy-database/SKILL.md for the full reasoning.
"""

import asyncio
import warnings
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    version     INTEGER NOT NULL DEFAULT 0,
    locale      TEXT NOT NULL DEFAULT 'en',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      INTEGER NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('daily', 'purchase', 'transfer', 'reward', 'correction')),
    idem_key    TEXT UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_user
    ON transactions (user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_transactions_idem
    ON transactions (idem_key)
    WHERE idem_key IS NOT NULL;
"""

MAX_RETRIES = 3  # CAS conflicts retried in transfer(), then RuntimeError.


async def connect(path: str) -> aiosqlite.Connection:
    # The default database lives in data/ (see config.DATABASE_PATH).
    # Create the parent directory first: SQLite cannot open a file in
    # a directory that does not exist, so a fresh checkout fails on
    # first run without this.
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(path)
    row = await (await db.execute("PRAGMA journal_mode=WAL")).fetchone()
    if row[0] != "wal":
        if row[0] == "memory":
            # A :memory: database has no journal file; that is expected
            # for tests, not a failure. Anything else means WAL did not
            # engage, and the bot must not run against it.
            warnings.warn("in-memory database: no WAL mode (test use only)")
        else:
            raise RuntimeError(f"could not enable WAL mode (got {row[0]!r})")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA synchronous=NORMAL")
    return db


async def init_db(db: aiosqlite.Connection) -> None:
    await db.executescript(SCHEMA)
    await db.commit()


async def get_balance(db: aiosqlite.Connection, user_id: int) -> int:
    cursor = await db.execute(
        "SELECT balance FROM users WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    return row[0] if row else 0


async def top_balances(
    db: aiosqlite.Connection, limit: int = 50
) -> list[tuple[int, int]]:
    """Richest users first: [(user_id, balance), ...], at most limit rows.

    Ordered by balance descending, then user id ascending. Zero
    balances are included when fewer than `limit` users have gold.
    """
    cursor = await db.execute(
        "SELECT user_id, balance FROM users "
        "ORDER BY balance DESC, user_id ASC LIMIT ?",
        (limit,),
    )
    return [(row[0], row[1]) async for row in cursor]


async def credit_once(
    db: aiosqlite.Connection,
    lock: asyncio.Lock,
    user_id: int,
    amount: int,
    kind: str,
    idem_key: str,
) -> bool:
    """Credit amount once. True if credited, False if the key was used before."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    async with lock:
        await db.execute("BEGIN IMMEDIATE")  # plain, NOT async with
        try:
            # User row first: the transactions table has a foreign key
            # on user_id, so the user must exist before the ledger row.
            await db.execute(
                "INSERT INTO users (user_id, balance) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?, version = version + 1",
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
        except Exception:
            await db.rollback()
            raise


async def transfer(
    db: aiosqlite.Connection,
    lock: asyncio.Lock,
    from_id: int,
    to_id: int,
    amount: int,
) -> None:
    """Move amount from one user to another, atomically.

    Compare-and-swap: the debit is one atomic UPDATE guarded by the
    sender's version, and rowcount proves it landed. Raises ValueError
    on insufficient funds; retries a version conflict (max 3), then
    gives up with RuntimeError instead of writing an unverified balance.
    See skills/economy-database/SKILL.md for the full reasoning.
    """
    if amount <= 0:
        raise ValueError("amount must be positive")
    if from_id == to_id:
        raise ValueError("cannot transfer to yourself")
    for _attempt in range(MAX_RETRIES):
        async with lock:
            await db.execute("BEGIN IMMEDIATE")
            try:
                cursor = await db.execute(
                    "SELECT balance, version FROM users WHERE user_id = ?",
                    (from_id,),
                )
                row = await cursor.fetchone()
                balance, version = (row[0], row[1]) if row else (0, 0)
                if balance < amount:
                    raise ValueError("insufficient funds")
                cur = await db.execute(
                    "UPDATE users SET balance = balance - ?, version = version + 1 "
                    "WHERE user_id = ? AND balance >= ? AND version = ?",
                    (amount, from_id, amount, version),
                )
                if cur.rowcount != 1:
                    # Someone else changed this row since we read it.
                    # Roll back and retry from a fresh read; do not guess.
                    await db.rollback()
                    continue
                await db.execute(
                    "INSERT INTO users (user_id, balance) VALUES (?, ?) "
                    "ON CONFLICT(user_id) DO UPDATE SET "
                    "balance = balance + ?, version = version + 1",
                    (to_id, amount, amount),
                )
                await db.execute(
                    "INSERT INTO transactions (user_id, amount, kind) "
                    "VALUES (?, ?, 'transfer')",
                    (from_id, -amount),
                )
                await db.execute(
                    "INSERT INTO transactions (user_id, amount, kind) "
                    "VALUES (?, ?, 'transfer')",
                    (to_id, amount),
                )
                await db.commit()
                return
            except Exception:
                await db.rollback()
                raise
    raise RuntimeError("transfer conflicted too many times; try again later")
