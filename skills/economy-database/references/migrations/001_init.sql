-- 001_init.sql — create the base economy tables.
-- Up: users + transactions + idx_transactions_user.
-- This is the first migration; it creates the tables as they were
-- before idem_key (002) and version/locale (003) existed.
-- The kind CHECK is declared here, at table creation: SQLite cannot
-- add a CHECK constraint with ALTER TABLE later.

CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      INTEGER NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('daily', 'purchase', 'transfer', 'reward', 'correction')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_user
    ON transactions (user_id, created_at);

-- Down (rollback): drop what this migration created. Only run on a
-- database with no user data in these tables.
--   DROP INDEX IF EXISTS idx_transactions_user;
--   DROP TABLE IF EXISTS transactions;
--   DROP TABLE IF EXISTS users;
