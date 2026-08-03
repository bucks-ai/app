-- =============================================================================
-- Seed: M4b — Sandbox-per-Business Execution (batch 2 of the M4 pivot; 9 tasks)
--
-- Run once in the Supabase SQL editor (the app project the runner polls).
--
-- M4b completes the pivot: a mission created from the app's Execute button is
-- actually executed by the runner against THAT business's own sandboxed
-- resources (own repo, scoped token, own Vercel project) — never against the
-- bucks-ai repo. It also closes every gap the M4a verification report and the
-- founder review surfaced.
--
-- FOUNDER PREREQUISITES:
--   - The three M4a schema files are applied (done 2026-07-10).
--   - After m4b-04 lands, its migration must be applied — but m4b-01 exists
--     precisely to make un-applied migrations impossible to miss from now on.
--
-- business_id / user_id are copied from the completed M4a mission row.
-- =============================================================================

WITH src AS (
  SELECT business_id, user_id
  FROM public.missions
  WHERE id = 'ff7dc6f0-aa68-4be2-8d3f-895d382c2208'  -- M4a — Runner-App Integration
),
m AS (
  INSERT INTO public.missions (business_id, user_id, name, goal, status, task_count)
  SELECT
    business_id,
    user_id,
    'M4b — Sandbox-per-Business Execution (batch 2)',
    'Complete the pivot: Execute-created missions run against the business''s own sandboxed repo, scoped credentials, and Vercel project under external containment — plus close every M4a verification gap (migrations wiring, Execute CTA, approvals empty state, live self-mission demo). Done when clicking Execute on a real business makes the runner build and deploy that business''s repo with live status in the UI.',
    'queued',
    9
  FROM src
  RETURNING id, business_id, user_id
)
INSERT INTO public.mission_tasks
  (mission_id, business_id, user_id, task_id, title, description, type, branch, position, status)
SELECT m.id, m.business_id, m.user_id,
       t.task_id, t.title, t.description, t.type, t.branch, t.position, 'queued'
FROM m,
(VALUES
  ('m4b-01-migrations-wiring',
   'M4b: un-applied migrations become impossible to miss',
   'Root cause of the M4a critical finding: tools/db_tools.py::apply_pending_migrations exists but nothing calls it, so merged additive migrations silently never reach production. Fix both halves: (1) add a graph step (or run-loop startup check) that, when DIRECT_DATABASE_URL is configured, compares supabase/migrations/ against the _runner_migrations ledger and logs a loud migrations_pending event (curated Slack set) listing un-applied filenames; (2) when AUTO_APPLY_MIGRATIONS=true (new config, default false, three-place rule) AND the file passes the existing sql_guard scan and sql_environment_gate policy, apply it via apply_pending_migrations and log migration_applied. Non-additive or guard-blocked files always alert, never auto-apply. Unit tests: pending-detection, auto-apply happy path, guard-blocked refusal, no-database no-op. Update supabase/migrations/README.md to describe the now-real automated path.',
   'backend', 'feature/m4b/migrations-wiring', 1),

  ('m4b-02-execute-cta-and-approvals-state',
   'M4b: Execute becomes the primary CTA; approvals empty state disambiguated',
   'Two founder-review findings. (1) Execute is currently a 10px mono chip the founder could not find: promote it to the primary action of the business Overview — a prominent button (design-system accent, normal button sizing) in the header area with mission status displayed inline beside it (queued/running/completed with tone colors), and a short helper line explaining what Execute does. Keep the ExecutePanel logic; this is presentation. (2) The Actions tab approvals panel cannot distinguish "no approvals pending" from "approvals schema missing": when the API classifies approvals_schema_missing, render an amber human-required notice naming the SQL file to apply; when genuinely empty, say "No approvals pending". Extend business-tabs E2E for the promoted CTA (use role/name selectors, exact matches — remember the strict-mode lessons) and unit tests for the two empty states.',
   'frontend', 'feature/m4b/execute-cta', 2),

  ('m4b-03-live-self-mission-demo',
   'M4b: live self-targeted mission proves claim -> agent_runs -> UI end to end',
   'Close the gap m4a-10 could not safely exercise from inside its own session. Add CLI command python main.py create-self-mission --title <t> --task <one-line task> that inserts a minimal runner_target=self mission (1 docs-type task) into Supabase for the bucks.ai business. Then, as this task''s own verification, create one and let the CURRENT loop claim it on a subsequent iteration: confirm fetch_next_queued_mission claims it, agent_run rows are streamed to production for its task (start -> complete), and the Operating Team UI shows the real run. Append a dated addendum to docs/M4A-VERIFICATION-REPORT.md with the observed row ids and a screenshot path. If claiming within the same session proves unsafe, document the exact constraint and verify via run-once in an isolated copy pointed at the REAL Supabase (the M4a report shows the pattern).',
   'backend', 'feature/m4b/self-mission-demo', 3),

  ('m4b-04-business-sandbox-config',
   'M4b: per-business sandbox configuration model',
   'The containment substrate. Additive migration supabase/migrations/0004_business_sandbox.sql: business_sandbox table (business_id FK unique, user_id FK, repo_full_name TEXT, vercel_project_id TEXT, github_token_secret_name TEXT, vercel_token_secret_name TEXT, status TEXT default unconfigured, timestamps, RLS owner-only, follows missions.sql style). CRITICAL: the table stores SECRET NAMES ONLY, never values — actual tokens live in the runner''s env/secret store under those names (external containment; document the convention in the README). App side: src/lib/sandbox.ts with typed accessors and a sandbox-status section on the business Settings tab showing configured/unconfigured per field (names only, never values). API route for the founder to set repo/project/secret-name fields (authenticated, zod, rate-limited). Unit tests app-side; RLS test extension for the new table.',
   'backend', 'feature/m4b/sandbox-config', 4),

  ('m4b-05-runner-foreign-repo-execution',
   'M4b: runner executes missions against a foreign (business) repo',
   'Teach the runner to work outside its own repo, safely. When a claimed mission''s business has sandbox config: clone/fetch repo_full_name into an isolated per-business workspace dir (runner/langgraph/.workspaces/<business_id>/, gitignored), override repo_path for that mission''s tasks, and use the GitHub token named by github_token_secret_name (read from env by that name; error with a resource-gate request naming the missing secret if absent — names only). Guardrails, unit-tested: a business mission must NEVER run with repo_path equal to the bucks-ai repo; the bucks-ai repo path is rejected as a sandbox repo_full_name; worker prompts for business missions state the target repo explicitly; existing protected-branch rules apply inside the workspace. The PR/merge flow reuses the existing github_tools with the scoped token. Tests with mocked git/HTTP covering workspace creation, path override, wrong-repo refusal, and missing-secret resource request.',
   'backend', 'feature/m4b/foreign-repo-execution', 5),

  ('m4b-06-business-vercel-deploy',
   'M4b: deploys and post-deploy checks target the business''s Vercel project',
   'When executing a business mission with sandbox config, deploy_if_needed and the Vercel polling in tools/vercel_tools.py must target the business''s vercel_project_id using the token named by vercel_token_secret_name — never the bucks-ai project. Post-deploy validation for business missions: a lightweight smoke check against the deployed business URL (HTTP 200 on /, non-empty title) via the existing playwright_harness/E2E plumbing, with the result logged per-URL (the m2-12 event shape). Unit tests with mocked Vercel API: correct project targeting, token selection by name, refusal to fall back to the bucks-ai project when sandbox config is partial.',
   'backend', 'feature/m4b/business-vercel-deploy', 6),

  ('m4b-07-claim-gate-lift',
   'M4b: runner claims business missions - only inside a complete sandbox',
   'Lift the M4a safety gate, replacing it with a stricter one. fetch_next_queued_mission may claim runner_target=business missions ONLY when ALL hold: (1) new config BUSINESS_EXECUTION_ENABLED=true (default false, three-place rule); (2) the mission''s business has sandbox status configured with repo, Vercel project, and both secret names present; (3) the named secrets actually resolve in the runner env. Any condition failing leaves the mission queued and logs a distinct business_mission_blocked event with the failing condition (names only). The mission compiler for business missions generates starter tasks appropriate to a FRESH scaffolded repo (build landing page section, wire analytics stub, deploy) rather than bucks-ai-specific tasks — extend src/lib/mission-compiler.ts accordingly. Unit tests: every refusal path, the full-config claim path, compiler output against a fresh-repo assumption.',
   'backend', 'feature/m4b/claim-gate-lift', 7),

  ('m4b-08-execute-end-to-end-demo',
   'M4b: the pivot demo - Execute builds and deploys a real business repo',
   'The M4 done-when, exercised live. Using the founder''s test business: provision its sandbox via the real flows (create-repo API for its repo, Vercel create-project for its project, founder-set secret names pointing at the scoped tokens in runner env), set BUSINESS_EXECUTION_ENABLED=true, click Execute in the real UI, and let the runner claim and execute the compiled starter tasks against the business repo: commits land in the business repo, its Vercel project deploys, the smoke check passes against the live business URL, agent_runs stream, and the Operating Team UI shows it. Capture screenshots and the mission/task row ids as evidence. If any step is blocked by a missing founder credential, stop and surface it via the resource gate rather than working around it. Scope guard: the ONLY app-repo changes allowed are bug fixes discovered during the demo, each noted in the summary.',
   'test', 'feature/m4b/execute-demo', 8),

  ('m4b-09-verification-report',
   'M4b: verification pass and M4 mission report',
   'Write docs/M4B-VERIFICATION-REPORT.md as the done-when evidence for the whole M4 pivot: what m4b-08 demonstrated live (with artifact paths), the state of every containment guarantee (wrong-repo refusal, secret-name-only storage, claim-gate conditions, deploy targeting) each mapped to its test or live proof, migrations wiring status (m4b-01) including whether 0004 was auto-applied or founder-applied, the Execute CTA and approvals UX fixes, and the recommended M5 business selection criteria based on what the execution pipeline can actually build today. State everything unverified explicitly. This report is the centerpiece of the YC proof corpus: write it so an outside reader could audit the claim "our system executes missions against customer repos under containment."',
   'test', 'feature/m4b/verification', 9)
) AS t(task_id, title, description, type, branch, position);
