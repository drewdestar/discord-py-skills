## Atomic transfer (compare-and-swap)

A transfer is a compare-and-swap, not a read-modify-write. Never read a balance into Python, do arithmetic on it, and write the result back. Two writers that both read the old balance both write a "new" balance, and the economy creates money. Instead, let the database do the arithmetic in one statement, guarded by a version number, and check that the statement actually changed a row.

First, add a version column. Every row carries the version of the last write that touched it:

```sql
ALTER TABLE users ADD COLUMN version INTEGER NOT NULL DEFAULT 0;
-- New databases: put `version INTEGER NOT NULL DEFAULT 0` in
-- references/schema.sql and in migration 001 instead.
```

Then transfer like this:

```python
MAX_RETRIES = 3

async def transfer(db, lock, from_id: int, to_id: int, amount: int) -> None:
    """Move amount from one user to another. Raises ValueError on
    insufficient funds. Retries on a version conflict, then gives up
    instead of writing a balance it has not verified."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    if from_id == to_id:
        raise ValueError("cannot transfer to yourself")
    for attempt in range(MAX_RETRIES):
        async with lock:
            await db.execute("BEGIN IMMEDIATE")
            try:
                row = await (await db.execute(
                    "SELECT balance, version FROM users WHERE user_id = ?",
                    (from_id,),
                )).fetchone()
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
```

- `UPDATE … WHERE balance >= ? AND version = ?` is the whole trick. The `WHERE` clause is the check and the `SET` is the write, in one atomic statement. If another writer got there first, the version no longer matches, `rowcount` is 0, and nothing is written. That is a conflict, not an error to swallow.
- `rowcount != 1` means "abort and retry", never "write it anyway". A retry re-reads the balance and version from scratch. Three retries, then fail loudly with `RuntimeError`. A transfer that retries forever can starve every other write; a transfer that silently succeeds after a conflict can create money.
- A conflict and insufficient funds are different failures. Insufficient funds is checked from the fresh read and raises `ValueError` immediately, with no retry. A conflict is retried. Do not collapse them into one error: retrying an insufficient-funds transfer is pointless, and reporting a conflict as "insufficient funds" lies to the user.
- `BEGIN IMMEDIATE` and the single-writer lock stay. CAS does not replace them; it is the guard that catches the case where the lock was bypassed — a second process, a maintenance script, a future Postgres port. One guard is a hope; two guards is a design. Under the shared lock, no second transfer runs in-process; `BEGIN IMMEDIATE` is the defence for a second connection or process.
- The same pattern applies to every balance write, not just transfers. An idempotent credit (see `references/idempotent-credit.md`) must also bump `version` in its `ON CONFLICT … DO UPDATE` clause, or the version stops meaning "the last write that touched this row".
- Start the transaction with a plain `await db.execute("BEGIN IMMEDIATE")`. Do not wrap it in `async with`: `db.execute()` returns a cursor, and `async with` on a cursor only closes it — it does not scope the transaction.
- Any exception rolls the whole transfer back (`except: await db.rollback(); raise`). Without the rollback the connection keeps the write lock after a failed transfer, and the next write on that connection fails or blocks. The ledger never shows half a transfer.
- A transfer to yourself is rejected up front. Without the guard, a self-transfer debits and credits the same row and writes two ledger rows that cancel out — noise at best, a double-spend probe at worst.
- Transfers have no `idem_key`: one transfer writes two ledger rows, and a single UNIQUE key cannot cover both. A retried interaction (double-click, slow network) replays the whole transfer and moves the money twice. Guard replays in the command handler — record the Discord interaction id in a processed set and refuse a second execution — before calling `transfer()`.
- This is etcd-style optimistic locking on a single row, not etcd's cluster-wide CAS: it holds within one database with one writer, with no lease, no fencing, and no multi-key compare. Do not present it as distributed.

A read-then-write balance update fails the race test (`references/race-test.md`): both requests read the old balance and both write, creating money. Only an atomic `UPDATE users SET balance = balance + ? … WHERE version = ?` with a `rowcount` check passes it. If the test fails, the economy is broken, no matter how correct the code reads.
