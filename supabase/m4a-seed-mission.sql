-- =============================================================================
-- Seed: M4a — Runner-App Integration (batch 1 of the M4 pivot; 10 tasks)
--
-- Run once in the Supabase SQL editor (the app project the runner polls).
--
-- M4 turns the runner from a dev-side tool into bucks.ai's execution engine.
-- Batch 1 (this file): M3 carry-overs + runner hardening from live incidents,
-- then runner->app status streaming, the in-app approval queue, and an
-- Execute button that creates missions (self-targeted only — the runner must
-- NOT touch foreign repos until M4b lands the sandbox-per-business model).
-- Batch 2 (M4b, seeded only after founder review of this batch): scoped
-- per-business tokens, per-business repo/Vercel targeting, end-to-end
-- Execute-to-deployed-business demo.
--
-- business_id / user_id are copied from the completed M3 mission row.
-- =============================================================================

WITH src AS (
  SELECT business_id, user_id
  FROM public.missions
  WHERE id = 'f4077d78-87d4-4f76-9c2f-562253960d79'  -- M3 — Analytics + Observation
),
m AS (
  INSERT INTO public.missions (business_id, user_id, name, goal, status, task_count)
  SELECT
    business_id,
    user_id,
    'M4a — Runner-App Integration (batch 1)',
    'Close the M3 gaps, harden the PR-checks path against GitHub event drops, then wire the runner into the app: task lifecycle streamed into the agent-runs tables, Operating Team UI showing real runs, an in-app approval queue mirroring outbox/inbox, and an Execute button that creates self-targeted missions. Done when a mission created from the UI is visibly executed by the runner with live status in the app.',
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
  ('m4a-01-intake-instrumentation',
   'M4a: wire intake_started and intake_submitted capture',
   'Close the instrumentation gap found by docs/M3-VERIFICATION-REPORT.md: the canonical events intake_started and intake_submitted exist in src/lib/analytics/events.ts but have no capture call sites. Fire intake_started once when the intake wizard first mounts (guard against re-render double-fires) and intake_submitted on successful submit, both through the existing typed client capture helper so the m3-04 test-traffic guard applies automatically. Update docs/M3-EVENT-TAXONOMY.md call-site table. Tests for the pure helpers where practical; build must pass with and without NEXT_PUBLIC_POSTHOG_KEY.',
   'frontend', 'feature/m4a/intake-instrumentation', 1),

  ('m4a-02-sentry-bug-fix',
   'M4a: fix production TypeError caught by Sentry (JAVASCRIPT-NEXTJS-1)',
   'Sentry issue JAVASCRIPT-NEXTJS-1: TypeError "Object [object Object] has no method updateFrom", 1 user affected. Use runner/langgraph/tools/sentry_tools.py or the Sentry UI to pull the full stack trace and breadcrumbs, locate the offending code path in src/, reproduce with a unit test that fails before the fix, fix it, and confirm the test passes. In the summary state the root cause in one sentence. If investigation shows the error originates in third-party or stale-deploy code rather than current main, document that finding instead of forcing a code change.',
   'backend', 'feature/m4a/sentry-bug-fix', 2),

  ('m4a-03-pr-checks-hardening',
   'M4a: poll_pr_checks distinguishes and recovers from missing check runs',
   'Live incident 2026-07-09: GitHub dropped workflow events overnight, leaving PR #64 with ZERO check runs ever scheduled; poll_pr_checks treated empty check_runs as not-complete-yet and burned full timeouts repeatedly. Harden tools/github_tools.py: (1) when check_runs is still empty after an initial grace window (config PR_CHECKS_EMPTY_GRACE_S, default 180), query the PR mergeable state; (2) if mergeable is CONFLICTING or the branch is behind, call the update-branch API (PUT /pulls/{n}/update-branch) once to refresh the merge ref and re-trigger workflows, log pr_branch_updated, and continue polling; (3) if still no runs after a second grace window, fail fast with distinct error pr_checks_no_runs (never the generic timeout) so the failure guard sees an actionable reason. Three-place rule for new config. Unit tests with mocked HTTP for all three paths; existing poll_pr_checks tests must keep passing.',
   'backend', 'feature/m4a/pr-checks-hardening', 3),

  ('m4a-04-session-local-attempt-counts',
   'M4a: make repeated-task attempt counts session-local',
   'Live incident 2026-07-09: task_attempt_counts persists in .runtime/state.local.json across run-loop sessions, so a task that exhausted attempts in a previous (externally-caused) failure cascade gets insta-blocked by the repeated-task guard on the next fresh launch. Mirror the existing fresh-session pattern in cmd_run_loop (main.py) by resetting task_attempt_counts (and any related repeated-task counters) at run-loop start, so the guard measures attempts within one session only. Unit test: a state file with prior attempt counts starts a new loop with an empty counter. Update the README guard documentation.',
   'backend', 'feature/m4a/session-attempt-counts', 4),

  ('m4a-05-verify-funnel-walkthrough',
   'M4a: execute the M3_VERIFY live funnel walkthrough',
   'Execute the walkthrough that m3-10 could not run: with PostHog env configured and M3_VERIFY=true (events stamped verification_run=true), drive the funnel once end-to-end against a local production build — signup, intake submit (now instrumented by m4a-01), blueprint generate and save, tool approval, repo-created and deploy events (fire the server capture points via their real API routes; fake AI allowed; GitHub/Vercel calls may be exercised against the real bucks-ai test resources already configured). Then confirm each event arrived via posthog_tools queries and append an addendum section to docs/M3-VERIFICATION-REPORT.md with the observed counts. If any capture point does not fire, fix it in this task. Success evidence: every canonical event shows count >= 1 with verification_run=true.',
   'test', 'feature/m4a/verify-funnel', 5),

  ('m4a-06-agent-runs-streaming',
   'M4a: stream runner task lifecycle into the agent-runs tables',
   'Wire the runner into the app data the Operating Team UI reads. Audit src/lib/agents/{registry,runs,status}.ts and the agent_runs / agent_activity_logs tables to learn the exact row shapes, then extend the runner (tools/seeded_mission_queue.py sync path and/or update_logs_and_state in graph.py) so that for seeded-mission tasks it writes: a run row on task start (agent identity mapped from task type, e.g. backend -> Engineering Brain), status updates on completion/failure with the worker summary digest, and cost/duration fields where available. Additive SQL migration file only if a column is genuinely missing (follow supabase/ conventions). Degrade silently when Supabase is not configured. Unit tests with mocked Supabase client covering start, complete, and fail transitions.',
   'backend', 'feature/m4a/agent-runs-streaming', 6),

  ('m4a-07-operating-team-real-runs',
   'M4a: Operating Team UI shows real runner runs',
   'Replace mock/registry-only data in the Operating Team tab for a business with real rows streamed by m4a-06: each agent card shows its latest real run (task title, status, started/completed, one-line summary), and a run-history view lists recent runs with status badges using the design system (amber=awaiting human, red=failed, minimal green). Preserve the existing empty states for businesses with no runs. Follow the operator-console aesthetic; no new dependencies. Extend the business-tabs E2E spec to assert the operating-team tab renders seeded or empty-state content without error.',
   'frontend', 'feature/m4a/operating-team-real-runs', 7),

  ('m4a-08-inapp-approval-queue',
   'M4a: in-app approval queue mirroring outbox/inbox',
   'Give the app the same approval power Slack has, using the same file conventions (never bypassing them). Runner side: extend the outbox scan (reuse tools/slack_approvals.py classification) to upsert pending approval requests into a new approvals table (additive migration, RLS owner-only, following supabase/missions.sql style), and poll that table for founder decisions, writing the SAME inbox fulfillment files the Slack daemon writes — the graph gates stay file-based and untouched. App side: an Approvals panel on the business Actions tab listing pending requests (type, request id, sanitized body) with Approve/Reject actions calling an authenticated API route that records the decision. Decisions are idempotent with the Slack daemon (whichever writes the inbox file first wins; existence check before write). Unit tests both sides: classification-to-row mapping, decision-to-inbox-file resolution, RLS on the new table.',
   'backend', 'feature/m4a/inapp-approvals', 8),

  ('m4a-09-execute-button',
   'M4a: Execute button creates a runner mission from the app',
   'The pivot MVP: POST /api/businesses/[id]/execute (authenticated, rate-limited, zod-validated) compiles the business blueprint into a mission: inserts a missions row + mission_tasks rows (reuse the task-shape conventions of the seeded M1-M3 missions; a small deterministic compiler from blueprint sections to 3-5 concrete starter tasks is sufficient — no LLM call required in this task). CRITICAL SAFETY: add a runner_target column to missions (additive migration, default value self) and gate tools/seeded_mission_queue.py so the runner ONLY claims missions with runner_target=self until M4b lands per-business sandboxing — a mission created for a customer business must sit visibly queued, never executed against the bucks-ai repo. UI: Execute button on the business page showing mission status (queued/running/completed) from the missions table. Tests: API validation, compiler output shape, the runner-side claim gate (a mission with runner_target=business is never claimed).',
   'backend', 'feature/m4a/execute-button', 9),

  ('m4a-10-verification-report',
   'M4a: verification pass and batch report',
   'End-to-end proof of the batch: create a small self-targeted mission via the new Execute flow (or directly via the API route) and verify the runner claims it, streams run rows into agent_runs (m4a-06), shows live status in the Operating Team UI (m4a-07), and that an approval created during the run appears in and is resolvable from the in-app queue (m4a-08). Verify the m4a-03 hardening with its unit tests and confirm m4a-04 by launching run-loop twice. Write docs/M4A-VERIFICATION-REPORT.md: what was exercised live vs unit-tested, screenshots/artifact paths where available, outstanding founder actions, and the recommended scope adjustments for M4b based on what this batch revealed. State missing credentials or blockers explicitly rather than silently passing.',
   'test', 'feature/m4a/verification', 10)
) AS t(task_id, title, description, type, branch, position);
