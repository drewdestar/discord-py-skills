"""SQLite economy layer for the starter bot.

One writer (one connection plus one asyncio.Lock), WAL mode, a ledger
table as the source of truth, and idempotency keys on every credit.
See skills/economy-database/SKILL.md for the full reasoning.
"""

import asyncio

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    idem_key    TEXT UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_user
    ON transactions (user_id, created_at);
"""


async def connect(path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(path)
    await db.execute("PRAGMA journal_mode=WAL")
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
        await db.execute("BEGIN IMMEDIATE")
        try:
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
        except aiosqlite.IntegrityError:
            await db.rollback()
            return False
    return True


async def transfer(
    db: aiosqlite.Connection,
    lock: asyncio.Lock,
    from_id: int,
    to_id: int,
    amount: int,
) -> None:
    """Move amount from one user to another, atomically."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    async with lock:
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?", (from_id,)
            )
            row = await cursor.fetchone()
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
        except Exception:
            await db.rollback()
            raise
