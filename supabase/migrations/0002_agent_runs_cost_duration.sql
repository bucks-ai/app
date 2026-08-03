-- =============================================================================
-- bucks.ai — agent_runs: cost + duration columns
-- =============================================================================
-- Adds the two columns the runner needs to stream per-run cost/duration data
-- (runner/langgraph/tools/agent_run_sync.py) into agent_runs. Neither existed
-- in supabase/agent-runs.sql (Agent Runs v1) — both are optional metrics, not
-- part of the core run lifecycle, so this is additive only.
--
-- Applied automatically by tools/db_tools.py::apply_pending_migrations. See
-- supabase/migrations/README.md for the migration ledger mechanics.
-- =============================================================================

ALTER TABLE public.agent_runs
  ADD COLUMN IF NOT EXISTS cost_usd NUMERIC,
  ADD COLUMN IF NOT EXISTS duration_seconds NUMERIC;

COMMENT ON COLUMN public.agent_runs.cost_usd IS
  'API cost in USD for this run, where known (e.g. worker api_cost for runner-driven runs).';
COMMENT ON COLUMN public.agent_runs.duration_seconds IS
  'Wall-clock duration of this run in seconds, where known.';
