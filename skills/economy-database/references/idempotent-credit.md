## Idempotent credit

```python
async def credit_once(db, lock, user_id: int, amount: int, kind: str, idem_key: str) -> bool:
    """Credit amount once. Returns True if credited, False if the key was already used."""
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
```

- The daily claim key is `daily:<user_id>:<YYYY-MM-DD>`. Retrying the same day returns False, so a double-click or a retried request never pays twice. The date in the key is UTC: `datetime.now(timezone.utc).date()`. A local date changes meaning when the bot's timezone does; UTC does not. One-line sketch: `key = f"daily:{user_id}:{datetime.now(timezone.utc).date().isoformat()}"`.
- The UNIQUE constraint on `idem_key` is what makes this safe under concurrency. Application-level "check then insert" is not safe; two requests can both check, both see nothing, and both insert.
- The `ON CONFLICT … DO UPDATE` bumps `version` too, or the version stops meaning "the last write that touched this row".
- An `IntegrityError` here means the `idem_key` was already used (the UNIQUE constraint). A kind outside the schema's CHECK fails the same way, so only pass the kinds the schema allows.
