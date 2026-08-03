-- =============================================================================
-- bucks.ai — business_sandbox: per-business sandbox configuration
-- =============================================================================
-- The containment substrate for M4b. Before the runner is ever allowed to
-- execute a mission against a business's OWN repo/Vercel project (rather than
-- the bucks-ai repo it runs from today), that business needs a sandbox
-- configuration row naming which repo, which Vercel project, and which named
-- secrets to use.
--
-- CRITICAL SAFETY: this table stores SECRET NAMES ONLY, never secret VALUES.
-- github_token_secret_name / vercel_token_secret_name are just strings naming
-- an entry in the runner's own env/secret store (looked up the same way
-- runner/langgraph/config.py reads GITHUB_TOKEN etc. via os.getenv) — the
-- actual GitHub/Vercel tokens never pass through Supabase or this table. See
-- the "Secret-name-only storage convention" section of this directory's
-- README.md for the full writeup.
--
-- Additive only (CREATE TABLE/INDEX IF NOT EXISTS), follows the RLS
-- owner-only pattern established in supabase/missions.sql. Unlike
-- missions.sql, there is deliberately no updated_at trigger here: recreating
-- a trigger idempotently normally needs a guarded statement first, but this
-- migrations/ directory is eligible for automated auto-apply
-- (tools/db_tools.py::classify_migration_additivity), which conservatively
-- classifies any such statement as non-additive regardless of its guard.
-- The app sets updated_at explicitly on every write instead
-- (src/lib/sandbox.ts::upsertSandboxConfig), mirroring
-- src/lib/tool-permissions.ts::upsertToolPermission.
--
-- Applied automatically by tools/db_tools.py::apply_pending_migrations. See
-- supabase/migrations/README.md for the migration ledger mechanics.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.business_sandbox (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id               UUID NOT NULL UNIQUE REFERENCES public.businesses(id) ON DELETE CASCADE,
  user_id                   UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Target repo for runner execution, e.g. "acme-inc/landing-page".
  repo_full_name            TEXT,

  -- Vercel project id the business's deploys target.
  vercel_project_id         TEXT,

  -- NAME of the env var / secret-store entry holding the scoped GitHub token
  -- for repo_full_name. Never the token value itself.
  github_token_secret_name  TEXT,

  -- NAME of the env var / secret-store entry holding the scoped Vercel token
  -- for vercel_project_id. Never the token value itself.
  vercel_token_secret_name  TEXT,

  -- unconfigured -> partial -> configured, derived from which fields above
  -- are set. See src/lib/sandbox.ts::computeSandboxStatus.
  status                    TEXT NOT NULL DEFAULT 'unconfigured',

  created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.business_sandbox
  ADD CONSTRAINT business_sandbox_status_check
  CHECK (status IN ('unconfigured', 'partial', 'configured'));

CREATE INDEX IF NOT EXISTS idx_business_sandbox_user_id
  ON public.business_sandbox(user_id);

CREATE INDEX IF NOT EXISTS idx_business_sandbox_status
  ON public.business_sandbox(status);

-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Owner-only, mirroring supabase/missions.sql: a founder can only read or
-- write the sandbox configuration for a business they own.
-- =============================================================================
ALTER TABLE public.business_sandbox ENABLE ROW LEVEL SECURITY;

CREATE POLICY "business_sandbox: select own"
  ON public.business_sandbox FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "business_sandbox: insert own"
  ON public.business_sandbox FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "business_sandbox: update own"
  ON public.business_sandbox FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "business_sandbox: delete own"
  ON public.business_sandbox FOR DELETE
  USING (auth.uid() = user_id);

COMMENT ON TABLE public.business_sandbox IS
  'Per-business sandbox configuration (M4b containment substrate). Stores which repo/Vercel project the runner may target for this business and the NAMES of the secrets holding scoped tokens for them — never the token values.';

COMMENT ON COLUMN public.business_sandbox.github_token_secret_name IS
  'Name of the env var / secret-store entry holding the scoped GitHub token for repo_full_name. Never store the token value here.';

COMMENT ON COLUMN public.business_sandbox.vercel_token_secret_name IS
  'Name of the env var / secret-store entry holding the scoped Vercel token for vercel_project_id. Never store the token value here.';
