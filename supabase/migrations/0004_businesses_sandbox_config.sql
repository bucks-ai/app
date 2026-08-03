-- =============================================================================
-- bucks.ai — businesses: sandbox_config column
-- =============================================================================
-- M4b: lets the runner execute a business's mission against that business's
-- OWN GitHub repo, in an isolated per-business workspace, instead of the
-- bucks-ai repo. A business only becomes eligible for foreign-repo execution
-- once this column is populated with:
--
--   {
--     "repo_full_name": "owner/name",
--     "github_token_secret_name": "SOME_ENV_VAR_NAME"
--   }
--
-- `repo_full_name` is the target GitHub repo the mission's tasks should run
-- against. `github_token_secret_name` is the NAME (never the value) of an
-- environment variable the runner process reads at dispatch time to get a
-- scoped GitHub token for that repo — see
-- runner/langgraph/tools/foreign_repo_workspace.py::resolve_scoped_github_token.
--
-- CRITICAL SAFETY: `repo_full_name` must never resolve to the bucks-ai repo
-- itself — runner/langgraph/tools/foreign_repo_workspace.py::is_bucks_ai_repo
-- refuses any sandbox_config that points at it, so a business mission can
-- never be executed against the runner's own source tree.
--
-- Additive only: existing rows default to NULL (no sandbox configured), which
-- keeps every business ineligible for foreign-repo execution until an
-- operator explicitly fills this in.
-- =============================================================================

ALTER TABLE public.businesses
  ADD COLUMN IF NOT EXISTS sandbox_config JSONB;

COMMENT ON COLUMN public.businesses.sandbox_config IS
  'Foreign-repo execution config for M4b: {"repo_full_name": "owner/name", "github_token_secret_name": "ENV_VAR_NAME"}. NULL means this business has no sandbox configured and its missions cannot be executed against a foreign repo. repo_full_name must never resolve to the bucks-ai repo itself.';
