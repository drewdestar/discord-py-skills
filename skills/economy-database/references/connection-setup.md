## Connection setup

```python
import warnings

import aiosqlite
from pathlib import Path

async def connect(path: str) -> aiosqlite.Connection:
    # Create the parent directory first: SQLite cannot open a file in
    # a directory that does not exist, so a fresh checkout (whose
    # database defaults to data/bot.db) fails on first run without this.
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
    await db.execute("PRAGMA busy_timeout=5000")  # wait 5s instead of failing at once
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA synchronous=NORMAL")
    return db

async def init_db(db: aiosqlite.Connection) -> None:
    """Create the tables (idempotent). Keep a copy of the pack's
    references/schema.sql next to db.py as schema.sql."""
    await db.executescript(Path(__file__).with_name("schema.sql").read_text())
    await db.commit()

async def get_balance(db: aiosqlite.Connection, user_id: int) -> int:
    row = await (await db.execute(
        "SELECT balance FROM users WHERE user_id = ?", (user_id,)
    )).fetchone()
    return row[0] if row else 0
```

- WAL mode is the single most important setting. In WAL mode, readers do not block writers and writers do not block readers, and there is still exactly one writer at a time in both modes. Without WAL, a read blocks a write and a write blocks every read, which is how bots freeze under load.
- `busy_timeout` turns a collision into a short wait instead of an immediate error.
- `synchronous=NORMAL` with WAL cannot corrupt the database, but it can lose the most recent committed transactions if the operating system crashes or the power fails. See "Backups" for the full durability window.
- Call order: `connect()` → `init_db()` for a fresh database, or `migrate()` for an existing one → use. Never use the connection before one of the two has run.
- Keep one long-lived connection per bot process and guard writes with an `asyncio.Lock`. Opening a connection per command is slow and invites interleaving.
