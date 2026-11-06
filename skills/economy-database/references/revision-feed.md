## Every mutation bumps a revision

Every balance change is ordered, replayable, and auditable. That takes one rule: every economy mutation bumps a monotonic revision, in the same transaction as the money movement. No mutation without a revision bump, no revision bump without a ledger row.

There are two revisions, and they do different jobs:

1. **A global sequence.** The `transactions` ledger is the audit log. Its `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`) is a monotonic sequence: ids are never reused after a delete, but they are not sequential — a failed or rolled-back insert leaves a gap. Treat that `id` as the global revision. Do not add a second global counter table unless you need one — a second counter is a second source of truth, and the two will disagree. (Pattern borrowed from etcd, Apache-2.0: one global 64-bit revision counter, every change consumes exactly one revision. The economy's version is the ledger row id.)
2. **A per-user version.** The `users.version` column from the transfer section is the per-row revision. Every write to a user row — transfer, credit, debit, refund — increments it by exactly one, in the same statement that moves the money. If a write moves money without bumping `version`, the CAS guard in the transfer section is blind to it.

Rules:

- Corrections are new rows, never edits. To fix a wrong credit, write a compensating ledger row (`kind = 'correction'`, negative amount), never `UPDATE transactions SET amount = …`. Rewriting history destroys the audit trail and makes "where did this gold come from?" unanswerable.
- The ledger is append-only. No `DELETE` on `transactions` outside a documented, whole-range retention prune (see the backup section's retention note), and never a row-by-row delete to "tidy up".
- The dashboard — and any audit feed — polls by revision, not by re-reading whole tables:

```sql
-- "Everything that changed since revision N", for the dashboard feed.
SELECT id, user_id, amount, kind, idem_key, created_at
FROM transactions
WHERE id > ?
ORDER BY id ASC
LIMIT 100;
```

  The dashboard keeps the highest `id` it has seen and asks for `id > last_seen`. If the numbers it receives are not consecutive, it missed events: it must re-sync with a full read instead of assuming nothing happened. A gap is a signal, not a rounding error.
- Do not use `created_at` as the sequence. Two rows can share a timestamp, and clocks move backwards. The ledger `id` is the order; the timestamp is decoration.
