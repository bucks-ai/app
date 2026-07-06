# supabase/migrations

Versioned, ordered SQL migrations applied automatically by the runner
(`runner/langgraph/tools/db_tools.py`) via a direct Postgres connection.

This replaces the older pattern of loose, manually-applied files directly
under `supabase/` (`schema.sql`, `missions.sql`, `research.sql`,
`agent-runs.sql`, `validation.sql`) — those remain as historical reference for
schema already applied by hand, but all *new* schema changes should be added
here as a new migration file.

## Naming convention

```
NNNN_description.sql
```

- `NNNN` — a zero-padded, strictly increasing 4-digit sequence number
  (`0001`, `0002`, `0003`, ...). This also defines application order —
  migrations are applied in filename-sorted order.
- `description` — short, lowercase, underscore-separated summary of what the
  migration does (e.g. `0002_add_agent_runs_index.sql`).
- One logical change per file. Do not edit a migration file after it has been
  applied anywhere (dev, staging, or production) — add a new migration
  instead, so the ledger's recorded `sha256` stays meaningful.

## How migrations are applied

- `db_tools.apply_migration_file(path)` applies a single file inside one
  transaction, gated by `tools/sql_guard.scan_sql_file` (blocks destructive
  statements) and `tools/sql_environment_gate` (requires human approval in
  restricted environments per `SQL_APPROVAL_POLICY`). On success it records
  `(filename, sha256, applied_at)` in the `_runner_migrations` ledger table
  (created automatically if absent) in the same transaction, so a failure
  anywhere rolls back both the migration and the ledger entry together.
- `db_tools.apply_pending_migrations(dir)` applies every `*.sql` file in this
  directory in filename order, skipping any filename already present in the
  `_runner_migrations` ledger.
- Both require `DATABASE_URL` (read) and `DIRECT_DATABASE_URL` (apply,
  preferred — falls back to `DATABASE_URL`) to be configured; without them,
  both functions no-op with a clear error.

## 0001_runner_migrations.sql

The ledger table itself. `db_tools.py` also creates this table automatically
(`CREATE TABLE IF NOT EXISTS`) the first time it applies or checks a
migration, so this file mainly documents the schema and lets it be applied
explicitly/idempotently like any other migration.
