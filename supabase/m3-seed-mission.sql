-- =============================================================================
-- Seed: M3 — Analytics + Observation (10 tasks)
--
-- Run once in the Supabase SQL editor (the app project the runner polls).
-- The runner's seeded mission queue picks up status='queued' missions and
-- executes tasks in position order.
--
-- business_id / user_id are copied from the completed M2 mission row so this
-- mission belongs to the same founder + business.
--
-- FOUNDER PREREQUISITES (provision BEFORE launching the loop, or tasks will
-- pause at the resource gate):
--   PostHog: project created; NEXT_PUBLIC_POSTHOG_KEY + POSTHOG_KEY in
--            .env.local (and Vercel), POSTHOG_PERSONAL_API_KEY +
--            POSTHOG_PROJECT_ID in .env.local and runner/langgraph/.env
--   Sentry:  org/project created; SENTRY_DSN + NEXT_PUBLIC_SENTRY_DSN in
--            .env.local/Vercel (m1-18 wired the code, DSN was pending);
--            SENTRY_AUTH_TOKEN + SENTRY_ORG + SENTRY_PROJECT in
--            runner/langgraph/.env
-- =============================================================================

WITH src AS (
  SELECT business_id, user_id
  FROM public.missions
  WHERE id = '20f627bf-3ce8-4110-8bfe-f4ace610f60e'  -- M2 — Verification Engine
),
m AS (
  INSERT INTO public.missions (business_id, user_id, name, goal, status, task_count)
  SELECT
    business_id,
    user_id,
    'M3 — Analytics + Observation',
    'Instrument the signup-to-deploy funnel end to end and give the runner eyes: PostHog event taxonomy, client and server capture, dashboards as code, and runner-side PostHog/Sentry reader tools. Done when the runner can answer "how many users reached a deployed repo this week" from one command.',
    'queued',
    10
  FROM src
  RETURNING id, business_id, user_id
)
INSERT INTO public.mission_tasks
  (mission_id, business_id, user_id, task_id, title, description, type, branch, position, status)
SELECT m.id, m.business_id, m.user_id,
       t.task_id, t.title, t.description, t.type, t.branch, t.position, 'queued'
FROM m,
(VALUES
  ('m3-01-event-taxonomy',
   'M3: canonical analytics event taxonomy',
   'Create src/lib/analytics/events.ts exporting a typed, frozen catalog of canonical funnel event names: user_signed_up, intake_started, intake_submitted, blueprint_generated, blueprint_saved, tool_approval_requested, tool_approved, repo_created, scaffold_prepared, vercel_project_created, deploy_succeeded. Each entry carries name (snake_case), description, and required property conventions (business_id where applicable; never email or other PII in properties). Write docs/M3-EVENT-TAXONOMY.md documenting the funnel order signup -> intake -> blueprint -> saved -> tool_approved -> repo -> deploy and the property conventions. Unit tests: names unique, snake_case, catalog frozen. No capture calls in this task. Forbidden scope: no runner changes, no new dependencies.',
   'backend', 'feature/m3/event-taxonomy', 1),

  ('m3-02-posthog-server-capture',
   'M3: server-side PostHog capture on API routes',
   'Create src/lib/analytics/server.ts wrapping posthog-node: capture(event from the m3-01 catalog, distinctId, properties). Complete no-op without POSTHOG_KEY (guard on env presence; never request credential values), never throws, never blocks the response, flush handled per Next.js instrumentation conventions. Wire server-side capture into: generate-blueprint success (blueprint_generated), save-blueprint (blueprint_saved), tool-permissions PATCH approve (tool_approved) and request (tool_approval_requested), github/create-repo success (repo_created), github/prepare-next-scaffold (scaffold_prepared), vercel/create-project (vercel_project_created), vercel/refresh-deployment-status the first time a deployment reports READY (deploy_succeeded). distinct id is the authenticated user id; include business_id property. Tests with a mocked PostHog client for each capture point plus the no-key no-op. Add posthog-node to package.json; document POSTHOG_KEY in .env.example.',
   'backend', 'feature/m3/server-capture', 2),

  ('m3-03-client-capture',
   'M3: client-side capture and identify',
   'Using the existing posthog-js dependency: initialize in instrumentation-client.ts guarded on NEXT_PUBLIC_POSTHOG_KEY (complete no-op without it), identify on login/signup with the Supabase user id only (no email), fire intake_started when the intake wizard first mounts, intake_submitted on submit, and user_signed_up after successful signup. Use the typed catalog from m3-01. Guard against double-firing on re-renders. Build and npm test must pass with and without the key. Document NEXT_PUBLIC_POSTHOG_KEY in .env.example.',
   'frontend', 'feature/m3/client-capture', 3),

  ('m3-04-e2e-analytics-guard',
   'M3: keep test traffic out of analytics',
   'Prevent E2E and seeded-test traffic from polluting analytics: when E2E_FAKE_AI is enabled, or the authenticated user email equals TEST_USER_EMAIL, both client and server capture must no-op. Centralize the guard next to the capture helpers so future capture points inherit it, and document the behavior in docs/M3-EVENT-TAXONOMY.md. Provide an explicit M3_VERIFY=true env override that re-enables capture but stamps every event with property verification_run=true (used once by m3-10). Unit tests for guard and override logic.',
   'backend', 'feature/m3/e2e-analytics-guard', 4),

  ('m3-05-funnel-dashboards-as-code',
   'M3: PostHog funnel dashboard provisioned from code',
   'Create scripts/analytics/provision-dashboards.ts (npm script analytics:provision) using the PostHog API with POSTHOG_PERSONAL_API_KEY + POSTHOG_PROJECT_ID + optional POSTHOG_HOST (default https://us.posthog.com): idempotently create (find-or-update by name, never duplicate) (1) a funnel insight user_signed_up -> intake_submitted -> blueprint_saved -> tool_approved -> repo_created -> deploy_succeeded, (2) a weekly trend of unique users with deploy_succeeded, (3) a dashboard named "bucks.ai core funnel" containing both. Skip cleanly with a clear message when env is absent - do not request credential values. Document the env names in .env.example and a README analytics section.',
   'infra', 'feature/m3/dashboards', 5),

  ('m3-06-runner-posthog-tools',
   'M3: runner-side PostHog reader tools',
   'Create runner/langgraph/tools/posthog_tools.py: query_event_count(event, days) and query_funnel(events, days) via the PostHog query API, plus pure format_analytics_summary(). New config POSTHOG_PERSONAL_API_KEY, POSTHOG_PROJECT_ID, POSTHOG_HOST following the three-place rule (config.py + README env table + at least one test). Use tools/http_retry for requests. Degrade to a clear error result without credentials, never raise. tests/test_posthog_tools.py with mocked HTTP only - no live calls in CI. Forbidden scope: no app changes.',
   'backend', 'feature/m3/runner-posthog', 6),

  ('m3-07-runner-sentry-tools',
   'M3: runner-side Sentry reader tools',
   'Create runner/langgraph/tools/sentry_tools.py: list_new_issues(since_iso) and issue_summary() via the Sentry REST API using SENTRY_AUTH_TOKEN, SENTRY_ORG, SENTRY_PROJECT (three-place rule). Plain requests via tools/http_retry - no new SDK dependency. Pure parsing/formatting functions unit-tested against fixture payloads in tests/test_sentry_tools.py; degraded no-op without credentials. Forbidden scope: no app changes.',
   'backend', 'feature/m3/runner-sentry', 7),

  ('m3-08-weekly-analytics-report',
   'M3: one-command weekly analytics report',
   'Compose the eyes into the M3 done-when artifact: runner/langgraph/tools/analytics_report.py builds a weekly report (funnel step counts, unique users reaching repo_created and deploy_succeeded this week, new Sentry issues since 7 days ago) written to outbox/analytics_report.txt, logged as analytics_report_ready (add to the curated Slack event set), and exposed as CLI command python main.py analytics-report. The report must answer "how many users reached a deployed repo this week" in a single clearly-labeled line. Unit tests for report formatting with fixture data; degraded sections render "not configured" rather than failing the whole report.',
   'backend', 'feature/m3/analytics-report', 8),

  ('m3-09-server-capture-signup',
   'M3: capture user_signed_up server-side at account creation',
   'Investigate the auth flow (signup route/auth callback) and capture user_signed_up server-side at the single reliable point where a new account first exists, with a signup_method property. Must respect the m3-04 test-traffic guard. Do not double-fire alongside the client event from m3-03 - pick one authoritative source, prefer server, and remove or de-duplicate the client event accordingly, updating the taxonomy doc. Tests with mocked capture.',
   'backend', 'feature/m3/signup-capture', 9),

  ('m3-10-verification-report',
   'M3: verification pass and mission report',
   'With PostHog env configured: run the funnel once end-to-end (signup through deploy status refresh, fake AI allowed) using M3_VERIFY=true so events land stamped verification_run=true, confirm the events appear via posthog_tools queries, run python main.py analytics-report and confirm the deployed-repo line is answerable, then write docs/M3-VERIFICATION-REPORT.md: event inventory and capture points, dashboard links, runner tool status, what remains not configured (e.g. Sentry if DSN still absent), and outstanding founder actions. This report is the M3 done-when evidence. If credentials are absent, state exactly what is missing in the summary rather than silently passing.',
   'test', 'feature/m3/verification', 10)
) AS t(task_id, title, description, type, branch, position);
