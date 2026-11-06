-- 002_add_idem_key.sql — idempotency keys on ledger rows.
-- Up: add the idem_key column, then enforce uniqueness with a partial
-- unique index (only non-NULL keys are indexed).
-- SQLite forbids ADD COLUMN ... UNIQUE ("Cannot add a UNIQUE column"),
-- so the uniqueness lives in the index, not in the column definition.
-- The final schema in references/schema.sql declares idem_key TEXT
-- UNIQUE as well; the two forms enforce the same rule, and a database
-- migrated through this file has the unique partial index instead of
-- the column-level UNIQUE (one fewer index, same guarantee).

ALTER TABLE transactions ADD COLUMN idem_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_idem
    ON transactions (idem_key)
    WHERE idem_key IS NOT NULL;

-- Down (rollback): needs SQLite 3.35+ for DROP COLUMN.
--   DROP INDEX IF EXISTS idx_transactions_idem;
--   ALTER TABLE transactions DROP COLUMN idem_key;
