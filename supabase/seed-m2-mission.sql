-- =============================================================================
-- MISSION M2 — Verification Engine (20 tasks)
-- Run in the Supabase SQL Editor AFTER applying, in this order:
--   1. supabase/m1-mission-task-description.sql  (adds the description column
--      this seed inserts into — the seed FAILS without it)
--   2. supabase/m1-rls-fixes.sql                 (M1 RLS gap fixes; m2-17 verifies)
--
-- Done-when (master plan §7): a login-breaking PR cannot merge; the runner
-- validates deployed previews. Tasks 17-20 close out M0.9/M1 findings.
-- =============================================================================

WITH u AS (
  SELECT id FROM auth.users WHERE email = 'buckstestuser2025@gmail.com' LIMIT 1
),
b AS (
  SELECT id FROM public.businesses
  WHERE user_id = (SELECT id FROM u)
  ORDER BY created_at ASC LIMIT 1
),
m AS (
  INSERT INTO public.missions (business_id, user_id, name, goal, status, source_file, task_count)
  SELECT
    b.id, u.id,
    'M2 — Verification Engine',
    'Playwright E2E suite over the five core user flows, running in CI on every PR and against Vercel preview URLs, with seeded test data, screenshot artifacts, and runner-side UI flow validation. Done when a login-breaking PR cannot merge and the runner validates deployed previews.',
    'queued',
    'seed-m2-mission.sql',
    20
  FROM u, b
  RETURNING id
)
INSERT INTO public.mission_tasks (mission_id, business_id, user_id, task_id, title, description, type, branch, position, status)
SELECT m.id, b.id, u.id, t.task_id, t.title, t.description, t.type, t.branch, t.position, 'queued'
FROM m, u, b, (VALUES

(1, 'm2-01-test-user-seed', 'backend', 'feature/m2/test-user-seed',
'M2: create the E2E test user and seed script',
'Create scripts/seed-e2e.ts (run via npm run seed:e2e) that idempotently creates or resets a dedicated test user from TEST_USER_EMAIL and TEST_USER_PASSWORD env vars using the Supabase service role, plus one deterministic demo business owned by that user with a saved blueprint. Re-running must produce the same state (delete and recreate the business data). Never runs against production data of other users; operates only on the test user id. Add a unit test for the reset logic where practical.'),

(2, 'm2-02-playwright-setup', 'test', 'feature/m2/playwright-setup',
'M2: add Playwright to the app with config and npm scripts',
'Install @playwright/test in the app repo. Create playwright.config.ts with baseURL from PLAYWRIGHT_BASE_URL (default http://localhost:3000), retries 2 in CI and 0 locally, trace on-first-retry, screenshot only-on-failure, video retain-on-failure, and an html + line reporter. Add npm scripts test:e2e and test:e2e:ui. Create an e2e/ directory with a trivial smoke spec (home page renders) proving the setup works. Document browser installation (npx playwright install chromium).'),

(3, 'm2-03-e2e-auth-flows', 'test', 'feature/m2/e2e-auth',
'M2: E2E specs for signup, login, bad-password, logout',
'In e2e/auth.spec.ts cover: signup with a unique throwaway email succeeds and lands on the dashboard; login with TEST_USER_EMAIL/TEST_USER_PASSWORD succeeds; login with a wrong password shows an error and does not navigate; logout returns to the landing page and protected pages redirect to login afterwards. Use the seeded test user from scripts/seed-e2e.ts. These specs are the core of the login-breaking-PR gate, so keep them free of flaky waits — use Playwright auto-waiting assertions only.'),

(4, 'm2-04-e2e-fake-ai-mode', 'backend', 'feature/m2/e2e-fake-ai',
'M2: deterministic AI fixture mode for E2E',
'Add an E2E_FAKE_AI env flag. When set to true AND the environment is not production, src/app/api/generate-blueprint/route.ts (and other AI-calling routes exercised by E2E) skip the real model call and return a deterministic fixture that passes the zod output schemas from M1. Guard hard against production use: the flag must be ignored when NODE_ENV is production and a warning logged. This makes intake-to-blueprint E2E fast, free, and deterministic. Add tests that the fixture validates against the schema and that production ignores the flag.'),

(5, 'm2-05-e2e-intake-blueprint', 'test', 'feature/m2/e2e-intake',
'M2: E2E spec for intake to blueprint flow',
'In e2e/intake.spec.ts, logged in as the test user with E2E_FAKE_AI=true: fill the intake form, submit, wait for the generated blueprint to render, assert its key sections appear, save it, and assert it shows up on the dashboard. This is the product core flow; failure here must fail CI.'),

(6, 'm2-06-e2e-dashboard', 'test', 'feature/m2/e2e-dashboard',
'M2: E2E spec for dashboard',
'In e2e/dashboard.spec.ts, logged in as the seeded test user: dashboard lists the seeded demo business card; clicking it opens the business detail page; the empty state renders correctly for a fresh user (create a second throwaway user in the spec for that assertion).'),

(7, 'm2-07-e2e-business-tabs', 'test', 'feature/m2/e2e-business-tabs',
'M2: E2E spec for business detail tabs',
'In e2e/business-tabs.spec.ts, using the seeded business: each tab or panel on the business detail page (research, validation, execution, operating team or agents) renders without error and shows either seeded data or its designed empty state. Assert no unhandled error boundaries or raw error text appear.'),

(8, 'm2-08-e2e-tool-queue', 'test', 'feature/m2/e2e-tool-queue',
'M2: E2E spec for tools page and permission flows',
'In e2e/tools.spec.ts, logged in as the test user: the tools page renders the permission queue; approving a pending tool permission updates its state in the UI; denying works likewise. Seed at least one pending tool-permission row in scripts/seed-e2e.ts to make this deterministic.'),

(9, 'm2-09-ci-e2e-workflow', 'infra', 'feature/m2/ci-e2e',
'M2: GitHub Actions E2E job on every PR',
'Add an e2e job to the existing App CI workflow (or a new .github/workflows/e2e.yml): install deps, npx playwright install chromium --with-deps, build the app, run the seed script against a CI database configuration, next start, run npm run test:e2e with E2E_FAKE_AI=true, and upload the playwright-report and test-results directories as artifacts on failure. Use repository secrets for TEST_USER and Supabase values, and document in the workflow file which secrets the founder must add in GitHub settings. Do not remove or rename the existing required checks.'),

(10, 'm2-10-e2e-preview-url', 'infra', 'feature/m2/e2e-preview',
'M2: run E2E against the Vercel preview deployment',
'Extend the CI e2e job (or add a second job) that waits for the Vercel preview deployment of the PR, resolves its URL via the Vercel API using VERCEL_TOKEN and VERCEL_PROJECT_ID secrets, and runs the Playwright suite against that URL with PLAYWRIGHT_BASE_URL set to it. Skip gracefully with a neutral notice when no preview exists. Local-build E2E from the previous task remains the blocking path; preview E2E may start as informational.'),

(11, 'm2-11-runner-ui-flows-config', 'backend', 'feature/m2/runner-ui-flows',
'M2: runner UI flow config for the five core flows',
'Create runner/langgraph/ui-flows.json consumed by tools/ui_flow_validator.py load_flows_from_file covering: login, signup, intake-to-blueprint (fake AI mode not available against prod deploys, so this flow only asserts the intake form renders and submits validation errors correctly), dashboard render, business tabs render. Verify run_ui_flow_validation picks the file up (UI_FLOW_VALIDATION_ENABLED=true) and that flow failures are logged with per-step detail. Add unit tests for the flow definitions using the existing pure helpers.'),

(12, 'm2-12-runner-e2e-deploy-url', 'backend', 'feature/m2/runner-e2e-url',
'M2: make runner post-deploy E2E actually target the deployed URL',
'Audit run_e2e_if_needed and run_ui_flow_validation_if_needed in runner/langgraph/graph.py plus the deploy_result URL plumbing: during M1 every run logged e2e_skipped reason deploy-not-ready or no-URL. Ensure a successful Vercel deploy produces a URL the harness uses, E2E_BASE_URL env override still wins, and add a runs.jsonl event that records which URL was validated. Add or extend unit tests with mocked deploy results.'),

(13, 'm2-13-screenshot-artifacts', 'backend', 'feature/m2/screenshots',
'M2: screenshot artifacts from runner browser validation',
'Extend runner/langgraph/tools/playwright_harness.py and ui_flow_validator.py to capture a screenshot on each flow failure into runner/langgraph/outbox/screenshots/ with timestamped filenames, and log the path in the corresponding runs.jsonl event. Cap retained screenshots (delete oldest beyond 100). Unit test the retention logic; browser capture itself may be covered by an integration test guarded on Playwright availability.'),

(14, 'm2-14-flaky-policy', 'test', 'feature/m2/flaky-policy',
'M2: flaky test policy and quarantine tag',
'Add a @flaky tag convention: specs tagged flaky run in a separate non-blocking CI step, and the main e2e job excludes them. Document the policy (when to tag, obligation to fix within one mission) in the E2E runbook section. Add a CI summary that lists quarantined tests so they stay visible.'),

(15, 'm2-15-e2e-runbook', 'docs', 'feature/m2/e2e-runbook',
'M2: write docs/M2-E2E-RUNBOOK.md',
'Document: how to run the suite locally (seed, env vars, npm scripts), how to debug with traces and the UI mode, how to add a new spec, the fake-AI mode and its production guard, the CI jobs and their secrets, the preview-URL job, the flaky policy, and the founder step for making e2e a required check on branch protection. Keep it under 200 lines and current with what the previous tasks actually built.'),

(16, 'm2-16-required-check-prep', 'infra', 'feature/m2/required-check',
'M2: make the e2e job branch-protection ready',
'Ensure the blocking e2e CI job has a stable, documented check name suitable for branch protection, fails fast and clearly on auth-flow breakage, and passes reliably on three consecutive re-runs of an unchanged commit (re-run via workflow dispatch). Update the runbook with the exact check name. The founder then adds it as a required status check in GitHub settings — a human-only step; note it in the task summary as the completion handoff.'),

(17, 'm2-17-rls-verify', 'test', 'feature/m2/rls-verify',
'M2: verify RLS fixes against the live database',
'Precondition (founder): supabase/m1-rls-fixes.sql has been applied in the SQL editor. Run the M1 RLS test script (from m1-22) against the live database using the anon key and test user; fix any still-failing policies with a follow-up additive migration file supabase/m2-rls-fixes.sql (do not weaken existing policies). If the test script cannot run because credentials are absent, mark clearly in the summary what is missing instead of silently passing.'),

(18, 'm2-18-dod-file-verification', 'backend', 'feature/m2/dod-file-verify',
'M2: DoD gate verifies claimed files actually exist',
'M0.9 finding: a worker claimed a file it never created and definition-of-done still warned rather than caught it specifically. Extend the definition-of-done gate in the runner so that when a worker summary lists files created or modified, the gate checks those paths exist in the working tree (or the diff) and flags mismatches as a distinct issue type dod_file_claim_mismatch. Keep it warn-only under the current non-strict mode. Unit tests with fabricated summaries.'),

(19, 'm2-19-strict-stop-investigation', 'backend', 'feature/m2/strict-stop',
'M2: fix seeded-queue strict stop reason',
'M1 ended with stop reason chatgpt_no_task even though SEEDED_MISSION_QUEUE_STRICT was expected to halt with seeded_queue_exhausted before consulting the planner. Reproduce with unit tests: when the strict flag is on and the seeded mission is exhausted, the loop must stop with seeded_queue_exhausted and never call the ChatGPT planner. Fix config plumbing or graph ordering as needed, following the three-place rule for any config changes.'),

(20, 'm2-20-verification-pass', 'test', 'feature/m2/verification-pass',
'M2: full verification pass and mission report',
'Run the complete E2E suite locally (seed, fake AI, all specs) and confirm the CI e2e job is green on this task PR. Then write docs/M2-VERIFICATION-REPORT.md summarizing: spec inventory and what each covers, CI jobs and their trigger conditions, runner-side validation status (UI flows, screenshots, deploy URL targeting), and the outstanding founder actions (branch protection required check, preview job secrets). This report is the M2 done-when evidence.')

) AS t(position, task_id, type, branch, title, description);

-- Verify:
-- SELECT name, status, task_count FROM public.missions ORDER BY created_at DESC LIMIT 1;
-- SELECT position, task_id, status FROM public.mission_tasks
--   WHERE mission_id = (SELECT id FROM public.missions WHERE name LIKE 'M2%' ORDER BY created_at DESC LIMIT 1)
--   ORDER BY position;
