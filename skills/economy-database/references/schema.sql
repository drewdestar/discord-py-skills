-- Schema for a discord.py bot economy.
-- Apply with the migrations pattern in the economy-database skill.
-- SQLite dialect. WAL mode and pragmas are set in application code.

CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    locale      TEXT NOT NULL DEFAULT 'en',
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

CREATE INDEX IF NOT EXISTS idx_transactions_idem
    ON transactions (idem_key)
    WHERE idem_key IS NOT NULL;
