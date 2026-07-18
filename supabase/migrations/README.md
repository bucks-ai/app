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

Every runner loop start runs `graph.check_pending_migrations_if_needed`
(right after the launch readiness scorecard, before any task is dispatched):

1. If no database is configured (`DATABASE_URL` / `DIRECT_DATABASE_URL` both
   unset), the check no-ops.
2. Otherwise it compares this directory against the `_runner_migrations`
   ledger and **always** logs a loud `migrations_pending` event (in the
   curated Slack notification set) listing any un-applied filenames — this
   fires whether or not auto-apply is on, so un-applied migrations can no
   longer go unnoticed.
3. If `AUTO_APPLY_MIGRATIONS=true` (default `false`), it walks the pending
   files in filename order and applies each one that is classified
   **additive-only** by `db_tools.classify_migration_additivity` — no `DROP`,
   `TRUNCATE`, `DELETE`, `UPDATE ... SET`, `RENAME`, or `ALTER COLUMN ...
   TYPE`. The first non-additive file, or one blocked by the SQL guard/
   environment gate below, stops the pass for that run (so later files are
   never applied out of order) and logs `migration_auto_apply_blocked` — it
   was already surfaced by `migrations_pending` for a human to apply by hand.

The underlying tools, used both by the startup check and available for manual
scripting:

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
- `db_tools.list_pending_migrations(dir)` is the read-only version — lists
  un-applied filenames without applying anything.
- `db_tools.classify_migration_additivity(sql_text)` is a pure classifier
  (`{"additive": bool, "reasons": [...]}`) used to decide auto-apply
  eligibility; non-additive changes always require a human to run
  `apply_migration_file`/`apply_pending_migrations` by hand.
- All of the above require `DATABASE_URL` (read) and `DIRECT_DATABASE_URL`
  (apply, preferred — falls back to `DATABASE_URL`) to be configured; without
  them, they no-op with a clear error.

See `runner/langgraph/README.md` (**Startup Migration Check**) for the full
node behavior.

## 0001_runner_migrations.sql

The ledger table itself. `db_tools.py` also creates this table automatically
(`CREATE TABLE IF NOT EXISTS`) the first time it applies or checks a
migration, so this file mainly documents the schema and lets it be applied
explicitly/idempotently like any other migration.

## 0004_business_sandbox.sql — secret-name-only storage convention

`business_sandbox` is the containment substrate for M4b: it lets a founder
tell the runner which repo and Vercel project belong to a given business, so
a future mission can be executed against that business's own resources
instead of the bucks-ai repo.

The table stores **secret NAMES only, never secret VALUES**:
`github_token_secret_name` and `vercel_token_secret_name` are just strings
naming an entry in the runner's own env/secret store (resolved the same way
`runner/langgraph/config.py` reads `GITHUB_TOKEN` etc. via `os.getenv`) — the
actual scoped GitHub/Vercel tokens for a business never pass through
Supabase, this table, or the app's API routes. This is external containment:
the app layer only ever handles *which* secret to use, never the secret
itself. Any future runner code that reads a business's sandbox config (e.g.
to clone its repo or deploy to its Vercel project) must resolve the token by
looking up that name in its own environment — never by reading a token value
out of this table, because no such value is ever written there.
