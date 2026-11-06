## Database tests

```python
import asyncio

import pytest

from db import connect, credit_once, get_balance, init_db, transfer


async def test_transfer_is_atomic(tmp_path):
    db = await connect(str(tmp_path / "test.db"))
    await init_db(db)
    try:
        lock = asyncio.Lock()  # one lock for the whole test, mirroring
        await credit_once(db, lock, 1, 100, "reward", "seed:1")  # one lock per process
        await transfer(db, lock, 1, 2, 40)
        assert await get_balance(db, 1) == 60
        assert await get_balance(db, 2) == 40
        with pytest.raises(ValueError, match="insufficient funds"):
            await transfer(db, lock, 1, 2, 1000)
        assert await get_balance(db, 1) == 60  # failed transfer changed nothing
        assert await get_balance(db, 2) == 40  # and the receiver too
    finally:
        await db.close()
```

- Each test gets a fresh temporary database (`tmp_path`). Tests that share one database file order-depend on each other and fail in confusing ways. The starter's `tests/test_db.py` uses the same shape as a fixture instead: a `database` fixture that connects, runs `init_db`, yields the connection, and closes it after the test — use the fixture when several tests share the setup, `try/finally` when one test needs its own.
- `:memory:` is per-connection — a second connection sees an empty database, and it cannot survive the restart the live checks require. Use a temporary file, not `:memory:`, whenever a test opens more than one connection or the live checks need the same database back.
- One lock for the whole test. A fresh `asyncio.Lock()` per call looks the same but guards nothing: the economy skill's one-lock rule applies to tests too.
- The last two assertions are the point of the test: a failed transfer must leave both balances untouched. A test that only checks the happy path does not test atomicity.
