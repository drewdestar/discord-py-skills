-- 003_add_user_version.sql — per-row revision + locale on users.
-- Up: version (the compare-and-swap guard, see the economy skill's
-- "Atomic transfer") and locale (belongs to the i18n skill; it lives
-- on users so one table serves both skills).
-- Both columns arrive in this migration because they shipped in the
-- same release; they are not related to each other.

ALTER TABLE users ADD COLUMN version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN locale TEXT NOT NULL DEFAULT 'en';

-- Down (rollback): needs SQLite 3.35+ for DROP COLUMN. Only drop
-- version once no live code reads it (deploy the previous release
-- first); locale may be dropped the same way.
--   ALTER TABLE users DROP COLUMN version;
--   ALTER TABLE users DROP COLUMN locale;
