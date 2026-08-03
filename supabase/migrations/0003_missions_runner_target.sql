-- =============================================================================
-- bucks.ai — missions: runner_target column
-- =============================================================================
-- CRITICAL SAFETY: the Execute button (POST /api/businesses/[id]/execute,
-- src/app/api/businesses/[id]/execute/route.ts) lets a founder create a
-- mission for ANY business, but until M4b lands per-business sandboxing the
-- runner must only ever act on the bucks-ai repo itself. This column lets a
-- mission declare its execution target so the runner-side claim gate
-- (runner/langgraph/tools/seeded_mission_queue.py::fetch_next_queued_mission)
-- can refuse to claim anything but self-targeted missions. A mission created
-- for a customer business (runner_target = 'business') must sit visibly
-- queued in the app and never be executed against the bucks-ai repo.
--
-- Additive only: existing rows default to 'self' (the only value the runner
-- has ever safely targeted), so this migration does not change behavior for
-- any mission already in flight.
--
-- Applied automatically by tools/db_tools.py::apply_pending_migrations. See
-- supabase/migrations/README.md for the migration ledger mechanics.
-- =============================================================================

ALTER TABLE public.missions
  ADD COLUMN IF NOT EXISTS runner_target TEXT NOT NULL DEFAULT 'self';

ALTER TABLE public.missions
  ADD CONSTRAINT missions_runner_target_check
  CHECK (runner_target IN ('self', 'business'));

CREATE INDEX IF NOT EXISTS idx_missions_runner_target
  ON public.missions(runner_target);

COMMENT ON COLUMN public.missions.runner_target IS
  'self = the runner may claim and execute this mission against the bucks-ai repo (dev/ops missions). business = created for a customer business via the Execute button; must sit queued and NEVER be claimed until M4b lands per-business sandboxing.';
