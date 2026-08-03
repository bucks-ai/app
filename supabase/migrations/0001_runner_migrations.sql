-- =============================================================================
-- bucks.ai — Runner migrations ledger
-- =============================================================================
-- Tracks which versioned migration files (this directory) have already been
-- applied, so `db_tools.apply_pending_migrations` can skip them idempotently.
-- Created automatically (CREATE TABLE IF NOT EXISTS) by db_tools.py the first
-- time it applies or checks a migration — this file documents the schema and
-- can also be applied explicitly like any other migration.

CREATE TABLE IF NOT EXISTS _runner_migrations (
    filename    TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
