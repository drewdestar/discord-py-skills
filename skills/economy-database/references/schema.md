## Schema

See `references/schema.sql` for the full schema. The core tables:

```sql
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
    amount      INTEGER NOT NULL,          -- positive for credit, negative for debit
    kind        TEXT NOT NULL CHECK (kind IN ('daily', 'purchase', 'transfer', 'reward', 'correction')),
    idem_key    TEXT UNIQUE,               -- NULL for plain transfers, set for credits
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_user
    ON transactions (user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_transactions_idem
    ON transactions (idem_key)
    WHERE idem_key IS NOT NULL;
```

- `balance >= 0` as a CHECK constraint: the database itself refuses to create negative money, even if application code has a bug.
- `idem_key` is UNIQUE: the database enforces idempotency, not just the code.
- `kind` makes every row explainable. "Where did this gold come from?" is answerable from the ledger alone. The CHECK limits it to the five kinds the pack uses; a kind outside that list is a bug, and the database rejects it instead of recording it.
- `version` is the per-row revision for compare-and-swap (see "Atomic transfer"). Every write to a user row bumps it by exactly one, in the same statement that moves the money.
- `locale` belongs to the `i18n` skill; it lives here so one `users` table serves both. See the `i18n` skill for how the locale is read and written.
- `idx_transactions_user` serves per-user history; `idx_transactions_idem` is a partial index (only non-NULL keys) for idempotency lookups, so the lookup never scans the ledger.
