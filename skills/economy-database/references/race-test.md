## Race test: two claims at once must not double-pay

Atomicity is a claim until a test proves it. Run two identical credits concurrently and assert the balance moved exactly once. The test opens two connections to the same file database on purpose: the bot runs one connection, but the test must prove the defence works when the lock is bypassed, so it must not share one lock between the two calls. A shared lock would serialise the calls in-process and the test would pass even for a check-then-insert implementation that creates money across connections.

```python
import asyncio
from datetime import datetime, timezone

async def test_concurrent_daily_pays_once(tmp_path):
    db1 = await connect(str(tmp_path / "test.db"))
    db2 = await connect(str(tmp_path / "test.db"))
    try:
        await init_db(db1)
        key = "daily:1:" + datetime.now(timezone.utc).date().isoformat()
        results = await asyncio.gather(
            credit_once(db1, asyncio.Lock(), 1, 100, "daily", key),
            credit_once(db2, asyncio.Lock(), 1, 100, "daily", key),
        )
        assert results.count(True) == 1
        assert await get_balance(db1, 1) == 100
    finally:
        await db1.close()
        await db2.close()
```

Two concurrent transfers from the same sender must also hold: together they exceed the balance, so exactly one succeeds, the balance never goes below zero, and the version advances by exactly the number of successful writes:

```python
async def test_concurrent_transfers_cannot_overdraw(tmp_path):
    db1 = await connect(str(tmp_path / "test.db"))
    db2 = await connect(str(tmp_path / "test.db"))
    try:
        await init_db(db1)
        await credit_once(db1, asyncio.Lock(), 1, 100, "reward", "seed:1")
        before = await (await db1.execute(
            "SELECT version FROM users WHERE user_id = ?", (1,)
        )).fetchone()
        results = await asyncio.gather(
            transfer(db1, asyncio.Lock(), 1, 2, 80),
            transfer(db2, asyncio.Lock(), 1, 3, 80),
            return_exceptions=True,
        )
        successes = [r for r in results if r is None]
        failures = [r for r in results if isinstance(r, ValueError)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert await get_balance(db1, 1) == 20
        after = await (await db1.execute(
            "SELECT version FROM users WHERE user_id = ?", (1,)
        )).fetchone()
        assert after[0] == before[0] + 1  # exactly one transfer succeeded
    finally:
        await db1.close()
        await db2.close()
```

- Run them with `pytest-asyncio` in `asyncio_mode = "auto"` (see the testing skill). `tmp_path` gives each run a fresh database; `connect`/`init_db`/`get_balance` are the helpers in `references/connection-setup.md`. A test that takes a bare `db` argument with no fixture cannot run — pytest has nothing to inject.
- The lock serialises writes in-process; `BEGIN IMMEDIATE` is the defence across connections. A read-then-write balance update fails these tests: both requests read the old balance and both write, creating money. Only an atomic `UPDATE users SET balance = balance + ? … WHERE version = ?` with a `rowcount` check passes them. If a test fails, the economy is broken, no matter how correct the code reads.
