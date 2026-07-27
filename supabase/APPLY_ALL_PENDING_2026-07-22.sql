-- =============================================================================
-- bucks.ai — Combined pending-migrations apply script (2026-07-22)
-- =============================================================================
-- Paste this whole file into the Supabase SQL editor (the app project the
-- runner polls) and run it ONCE. It applies all 6 migrations the runner
-- reported as pending, in order:
--   0001_runner_migrations, 0002_agent_runs_cost_duration,
--   0003_missions_runner_target, 0004_business_sandbox,
--   0004_businesses_sandbox_config, 0005_business_sandbox_config_vercel_target
--
-- Every statement is guarded (IF NOT EXISTS / DROP-then-CREATE for policies /
-- DO-block for constraints), so running it a second time is harmless.
-- All additive: no DROP TABLE / TRUNCATE / DELETE FROM — safe on live data.
-- =============================================================================

-- ---- 0001: runner migrations ledger -----------------------------------------
CREATE TABLE IF NOT EXISTS _runner_migrations (
    filename    TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- 0002: agent_runs cost + duration ---------------------------------------
ALTER TABLE public.agent_runs
  ADD COLUMN IF NOT EXISTS cost_usd NUMERIC,
  ADD COLUMN IF NOT EXISTS duration_seconds NUMERIC;

COMMENT ON COLUMN public.agent_runs.cost_usd IS
  'API cost in USD for this run, where known (e.g. worker api_cost for runner-driven runs).';
COMMENT ON COLUMN public.agent_runs.duration_seconds IS
  'Wall-clock duration of this run in seconds, where known.';

-- ---- 0003: missions.runner_target -------------------------------------------
ALTER TABLE public.missions
  ADD COLUMN IF NOT EXISTS runner_target TEXT NOT NULL DEFAULT 'self';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'missions_runner_target_check'
  ) THEN
    ALTER TABLE public.missions
      ADD CONSTRAINT missions_runner_target_check
      CHECK (runner_target IN ('self', 'business'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_missions_runner_target
  ON public.missions(runner_target);

COMMENT ON COLUMN public.missions.runner_target IS
  'self = the runner may claim and execute this mission against the bucks-ai repo (dev/ops missions). business = created for a customer business via the Execute button; must sit queued and NEVER be claimed until M4b lands per-business sandboxing.';

-- ---- 0004: business_sandbox table -------------------------------------------
CREATE TABLE IF NOT EXISTS public.business_sandbox (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id               UUID NOT NULL UNIQUE REFERENCES public.businesses(id) ON DELETE CASCADE,
  user_id                   UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  repo_full_name            TEXT,
  vercel_project_id         TEXT,
  github_token_secret_name  TEXT,
  vercel_token_secret_name  TEXT,
  status                    TEXT NOT NULL DEFAULT 'unconfigured',
  created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'business_sandbox_status_check'
  ) THEN
    ALTER TABLE public.business_sandbox
      ADD CONSTRAINT business_sandbox_status_check
      CHECK (status IN ('unconfigured', 'partial', 'configured'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_business_sandbox_user_id
  ON public.business_sandbox(user_id);
CREATE INDEX IF NOT EXISTS idx_business_sandbox_status
  ON public.business_sandbox(status);

ALTER TABLE public.business_sandbox ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "business_sandbox: select own" ON public.business_sandbox;
CREATE POLICY "business_sandbox: select own"
  ON public.business_sandbox FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "business_sandbox: insert own" ON public.business_sandbox;
CREATE POLICY "business_sandbox: insert own"
  ON public.business_sandbox FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "business_sandbox: update own" ON public.business_sandbox;
CREATE POLICY "business_sandbox: update own"
  ON public.business_sandbox FOR UPDATE
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "business_sandbox: delete own" ON public.business_sandbox;
CREATE POLICY "business_sandbox: delete own"
  ON public.business_sandbox FOR DELETE
  USING (auth.uid() = user_id);

COMMENT ON TABLE public.business_sandbox IS
  'Per-business sandbox configuration (M4b containment substrate). Stores which repo/Vercel project the runner may target for this business and the NAMES of the secrets holding scoped tokens for them — never the token values.';

-- ---- 0004: businesses.sandbox_config column ---------------------------------
ALTER TABLE public.businesses
  ADD COLUMN IF NOT EXISTS sandbox_config JSONB;

-- ---- 0005: extend sandbox_config docs (Vercel keys) -------------------------
COMMENT ON COLUMN public.businesses.sandbox_config IS
  'Foreign-repo + Vercel deploy target config for M4b: {"repo_full_name": "owner/name", "github_token_secret_name": "ENV_VAR_NAME", "vercel_project_id": "prj_xxx", "vercel_token_secret_name": "ENV_VAR_NAME"}. NULL or any missing key disables that piece of foreign execution for the business.';

-- ---- Record all 6 in the runner ledger so the startup check passes ----------
-- sha256 is a sentinel ('manual-apply') — the check only cares that the
-- filename is present in the ledger, marking it applied.
INSERT INTO _runner_migrations (filename, sha256) VALUES
  ('0001_runner_migrations.sql',                 'manual-apply-2026-07-22'),
  ('0002_agent_runs_cost_duration.sql',          'manual-apply-2026-07-22'),
  ('0003_missions_runner_target.sql',            'manual-apply-2026-07-22'),
  ('0004_business_sandbox.sql',                  'manual-apply-2026-07-22'),
  ('0004_businesses_sandbox_config.sql',         'manual-apply-2026-07-22'),
  ('0005_business_sandbox_config_vercel_target.sql', 'manual-apply-2026-07-22')
ON CONFLICT (filename) DO NOTHING;
