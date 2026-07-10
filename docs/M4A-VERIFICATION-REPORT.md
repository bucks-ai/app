# M4a Verification Report

Mission: **M4a — Runner-App Integration (batch 1)**. This is the done-when
evidence for `m4a-10-verification-report`. It records what was actually
exercised live against the real production Supabase project
(`jrnzxeofqxuwodzivayo`) and the real production app
(`https://bucks-ai-app-archive.vercel.app/`) on 2026-07-10, what was only
unit-tested, and the founder actions this pass surfaced.

## Verdict

- **m4a-03 (PR-checks hardening) and m4a-04 (session-local attempt counts):
  fully verified, both live and by test.** No gaps found.
- **m4a-06 (agent-runs streaming), m4a-08 (in-app approvals), and m4a-09
  (Execute button / `runner_target` safety gate): correctly built and fully
  unit-tested, but three additive SQL files that ship the schema these
  features depend on were never applied to production.** This is the
  headline finding of this pass — see "Critical finding" below. It is not a
  code bug in any of the three tasks; it is a deployment step (documented in
  each SQL file's own header as founder-manual) that never happened.
- **m4a-07 (Operating Team UI): verified live, working exactly as designed**
  — it renders real registry/business-derived status for all 21 agents and
  correctly reports "no runner run recorded" for every one of them, because
  (per the finding above) no real `agent_runs` row has ever been written in
  production.
- **The one thing this task's own description assumed that turned out to be
  false:** a mission created via the Execute flow can never be
  self-targeted. `src/lib/missions.ts` hardcodes `runner_target: "business"`
  on every Execute-created mission, by design (see m4a-09's own
  "CRITICAL SAFETY" comment) — that gate is exactly what keeps a mission
  created for a customer business from ever being claimed by the runner. So
  "create a small self-targeted mission via the Execute flow" is not
  something the current code can do, on purpose. See "What could not be
  verified" below for how this was worked around.

## Critical finding: three schema files were never applied to production

Directly queried the live Supabase project with the service-role key
(read-only probes unless noted). All three of the following are additive
`CREATE`/`ALTER` files already merged to `main`, each carrying an explicit
"Arnav must run this file in the Supabase SQL Editor" header — this is the
established convention in this repo (see `supabase/agent-runs.sql`,
`supabase/missions.sql`) for schema that intentionally is not auto-applied.
None have been run yet:

| File | What it adds | Live status |
|---|---|---|
| `supabase/migrations/0003_missions_runner_target.sql` | `missions.runner_target` column (the entire m4a-09 safety gate) | **Missing.** `select id,runner_target from missions` → `column missions.runner_target does not exist` (PostgREST `42703`) |
| `supabase/migrations/0002_agent_runs_cost_duration.sql` | `agent_runs.cost_usd`, `agent_runs.duration_seconds` | **Missing.** Same error pattern, confirmed live |
| `supabase/m4a-approvals-queue.sql` | the entire `public.approvals` table (m4a-08) | **Missing entirely.** `select id from approvals` → `PGRST205: Could not find the table 'public.approvals' in the schema cache` |

The `_runner_migrations` ledger table (the automated-apply mechanism
described in `supabase/migrations/README.md`) exists but has **zero rows**,
and nothing in `graph.py` actually calls
`tools/db_tools.py::apply_pending_migrations` — the automated path described
in that README is unwired, so the manual-apply convention documented in each
file's own header is, in practice, the only path that was ever going to
apply these three files. That step just hasn't happened yet.

Concrete, live consequences, all reproduced against production during this
pass:

1. **The Execute button is completely non-functional in production.**
   Logged in as the seeded e2e user, opened "Seeded Demo Co", clicked
   Execute. The UI shows the error inline (does not crash):
   > Could not find the 'runner_target' column of 'missions' in the schema
   > cache
   Captured network trace: `POST /api/businesses/8677b28c-.../execute` →
   `500 {"ok":false,"error":"Could not find the 'runner_target' column of
   'missions' in the schema cache","code":"mission_create_failed"}`.
   Screenshot: `runner/langgraph/outbox/m4a-10-screenshots/13-execute-error-fullscreen.png`.
   Raw trace: `runner/langgraph/outbox/m4a-10-screenshots/execute-network-log.json`.
2. **The runner-side `runner_target` claim gate
   (`fetch_next_queued_mission`) errors on every call against production**
   — but **fails closed**: the error is caught, logged as
   `seeded_mission_queue_error`, and the function returns `None`, so the
   caller behaves as "no mission available" rather than unsafely claiming
   anything. Confirmed by calling the real function directly. No safety
   violation occurred; the safety property just isn't exercised by anything
   real yet.
3. **Zero real `agent_runs` rows exist in production**, ever, despite the
   entire m1–m4a-09 batch having genuinely executed live through this
   runner. `agent_runs` itself (from the older, already-applied
   `supabase/agent-runs.sql`) exists and its write path works — proven by a
   direct, live call to `tools/agent_run_sync.start_agent_run` /
   `complete_agent_run` against production with the M4a mission's real
   `business_id`/`user_id`, which inserted and completed a real row end to
   end. **That probe row was deleted immediately after confirming the
   shape** (`fc2e940f-84a5-46e7-befa-051829dcfd6e`, verified gone). So the
   write path itself is not broken; it simply has never fired for a real
   task, because every real seeded-mission task in this batch was fetched
   into the local queue in one shot at the start of the M4a batch (2026-07-09),
   before the code path that requires `runner_target` was reachable again —
   the *next* time the local queue empties and the runner goes back to
   Supabase for a new mission, that fetch will fail (safely) until the
   migration is applied.
4. **The Operating Team UI correctly reflects all of this.** Every one of
   the 21 agent cards for "Seeded Demo Co" shows "LATEST REAL RUN: No
   runner run has been recorded for this agent yet" — because none exist.
   Status badges (`COMPLETED`/`READY`/etc.) come from business-state
   "registry signal" inference, not from `agent_runs`, exactly as
   `src/lib/agents/runs.ts` is designed to do when no real run exists yet.
   This is the UI working correctly on top of an empty table, not a UI bug.
   Screenshot: `outbox/m4a-10-screenshots/06-operating-team-tab.png`, text
   dump: `outbox/m4a-10-screenshots/06-operating-team-body.txt`.
5. **The Approvals panel degrades gracefully**, live, confirmed by actually
   hitting it: `GET /api/approvals` returns `200 {"ok":true,"data":
   {"approvals":[]}}` rather than a 500, because `getPendingApprovalsForOwner`
   (`src/lib/approvals.ts`) specifically classifies "table not found" as
   `approvals_schema_missing` and the route (`src/app/api/approvals/route.ts`)
   maps that to an empty list. This was clearly a deliberate design decision
   in m4a-08, anticipating exactly this scenario — worth calling out as good
   practice, not just a lucky accident. The visible cost: a founder looking
   at the empty "Actions" tab cannot currently tell "no approvals pending"
   apart from "approvals feature isn't wired up yet." Screenshot:
   `outbox/m4a-10-screenshots/05-approvals-panel.png`.

## What was verified live

Run from `runner/langgraph/` and from the app root, against real production
Supabase/GitHub credentials already present in `.env` (no credentials were
missing for this pass):

1. **m4a-03 (`poll_pr_checks` hardening).** Read `tools/github_tools.py:332-443`
   — matches the spec exactly (`PR_CHECKS_EMPTY_GRACE_S` grace window,
   `pr_branch_updated` on `dirty`/`behind` mergeable state,
   `pr_checks_no_runs` as a distinct fail-fast reason). Confirmed the
   three-place config rule: `config.py:144`, `README.md:314,574-578`,
   `tests/test_pr_merge_flow.py:702,726`. `python -m pytest
   tests/test_pr_merge_flow.py` → **27 passed**, including
   `test_pr_merge_checks_no_runs_marks_task_failed_distinctly`.
2. **m4a-04 (session-local attempt counts).** Read `main.py:139-184`
   (`start_fresh_session`) — matches spec. Unit tests pass (`python -m
   pytest tests/test_run_loop_session_reset.py
   tests/test_repeated_error_guard.py` → **27 passed**). Additionally
   **launched the real `python main.py run-loop` CLI twice**, live, in an
   isolated `/tmp` copy of `runner/langgraph` (own `.runtime/`, empty task
   queue so no worker was ever dispatched) seeded each time with stale
   `task_attempt_counts`/`loop_count`/`stop_reason` from a simulated prior
   crash. Both runs reset `task_attempt_counts` to `{}` and `loop_count` to
   `0` before doing anything else, confirmed by reading the resulting state
   file after each run. (See "Why an isolated copy" below for why this
   wasn't run against the live orchestrator's own state file.)
3. **m4a-06/m4a-08/m4a-09 unit suites.** `python -m pytest tests/ -k
   "agent_run or seeded_mission or app_approval or mission_compiler or
   missions"` → **152 passed**. Full runner suite: `python -m pytest tests/`
   → **1699 passed**, 0 failed. Full app suite: `npx vitest run` → **348
   passed, 2 skipped**, 0 failed.
4. **m4a-07's own e2e assertion**, live against the local dev server wired
   to real production Supabase: `npx playwright test
   e2e/business-tabs.spec.ts` → **1 passed** (research/validation/execution/
   operating-team tabs render seeded data or empty state, never an error).
5. **Full live Execute → Operating Team → Approvals walkthrough** via a
   logged-in browser session (Playwright, headless Chromium) as the seeded
   e2e user against `Seeded Demo Co`: dashboard → business overview →
   Execute click → Actions tab (Approvals) → Team tab (Operating Team).
   Screenshots and raw response/text dumps for every step are in
   `runner/langgraph/outbox/m4a-10-screenshots/` (gitignored, listed at the
   end of this report).
6. **`agent_runs` write path**, live: a direct call to
   `tools.agent_run_sync.start_agent_run`/`complete_agent_run` against
   production with real FKs succeeded end to end (insert → update →
   read-back confirmed full row shape) and was cleaned up immediately after.
   This is what confirms finding #3 above is a "never fired yet" gap, not a
   broken write path.

## What could not be verified

- **A self-targeted mission created via the Execute flow.** Not possible by
  design (see Verdict). What this pass did instead: (a) exercised the real
  Execute flow end-to-end and captured its real, current failure mode
  (missing column) as the concrete state of that feature today, and (b)
  verified the runner-side self-targeted claim query
  (`fetch_next_queued_mission`) directly against production and confirmed
  it fails closed. It was **not** possible to observe the runner claim a
  brand-new self-targeted mission, stream a real `agent_runs` row for it,
  and show it live in the Operating Team UI within this pass, because (i)
  the schema gap above blocks the claim query outright, and (ii) this
  worker session is itself the currently-dispatched task for the live
  orchestrator's `.runtime/state.local.json` — invoking `run-loop`/`run-once`
  against that same live state file from inside this same session risks a
  recursive/duplicate worker dispatch against the very task this report is
  the output of, so it was deliberately not done (see next section).
- **An approval created during a run and resolved from the in-app queue.**
  Not exercisable: the `approvals` table doesn't exist in production yet.
  `PATCH /api/approvals/[id]` and `app_approvals_daemon.py`'s inbox-sync
  path are covered only by their existing mocked-Supabase unit tests
  (`tests/test_app_approvals.py`, `tests/test_app_approvals_daemon.py`,
  `src/lib/approvals.test.ts`), all passing.

### Why an isolated copy, not the live orchestrator, for the run-loop check

`runner/langgraph/.runtime/state.local.json` is a single hardcoded path
(`Path(__file__).parent.parent`, `tools/log_tools.py:7-10`) shared by every
invocation of this runner in this checkout — there is no env-var override.
At the time of this task, that file's `current_task_id` was
`m4a-10-verification-report` (this very task) with `current_worker: "claude"`
— i.e. the live orchestrator that dispatched this worker session is
currently blocked waiting on this session's own structured summary.
Invoking `run-loop`/`run-once`/`dry-run` from inside this same session
against that same file would resume the live graph mid-flight while this
worker is still the one it's waiting on, risking a second, nested worker
dispatch (real branch/PR/merge/deploy side effects, `AUTO_MERGE=true`,
`AUTO_DEPLOY=true`) as an unintended side effect of a verification task. The
m4a-04 check was instead run against a full, isolated `/tmp` copy of
`runner/langgraph` (own `.env`, own `.runtime/`, empty task queue) so the
real CLI command could be exercised twice, live, with zero risk to the
in-flight orchestration state or to production systems.

## Outstanding founder actions

1. **Apply the three pending SQL files to production**, in this order (all
   additive, all already reviewed/merged, all explicitly written for manual
   application):
   - `supabase/migrations/0002_agent_runs_cost_duration.sql`
   - `supabase/migrations/0003_missions_runner_target.sql`
   - `supabase/m4a-approvals-queue.sql`
   This single step unblocks the Execute button, the `runner_target` safety
   gate, and the entire in-app approvals feature simultaneously.
2. **Decide the migration-apply story going forward.** Either commit fully
   to "founder runs SQL Editor manually, always" (matches every file's own
   header) and remove/relabel the unused automated-ledger mechanism in
   `tools/db_tools.py` + `supabase/migrations/README.md` so it stops
   implying auto-apply that doesn't happen; or actually wire
   `apply_pending_migrations` into the graph. Recommend adding a cheap
   startup/preflight check (a graph node or a `main.py setup` check) that
   diffs `supabase/migrations/*.sql` filenames against the live schema and
   logs a loud warning when one looks unapplied — this exact class of gap
   (schema promised in merged code, silently absent in prod for days) is
   what caused every live-verification gap in this report.
3. **Re-run the live Execute → agent_runs → Operating Team → Approvals
   walkthrough** once (1) lands — this report's "what could not be
   verified" section should collapse to nothing at that point.

## Recommended scope adjustments for M4b

- **Sequence the schema fix as a same-day pre-M4b hotfix, not part of M4b's
  own scope.** M4b (per-business sandboxing) builds directly on
  `runner_target`; starting it before founder action #1 lands means
  building on top of a feature (Execute) that 500s on every use today.
- **Add a schema-drift smoke test to this repo's own DoD gate** — e.g. a
  test that opens a real (or CI-provisioned) Supabase connection and asserts
  every column/table referenced by `runner/langgraph/tools/*.py` and
  `src/lib/*.ts` actually exists. This is the single change most likely to
  have caught this batch's core gap before it shipped.
- **Surface `cost_usd`/`duration_seconds` in the app**, once columns exist —
  currently zero references to either field anywhere in `src/`, so even
  after the migration lands, the Operating Team UI won't show them without
  a small follow-up in `src/lib/agents/runs.ts` and the run-card component.
- **Harden `fetch_next_queued_mission`'s fail-closed behavior with an
  explicit test** for "column doesn't exist" specifically (today's tests
  cover `runner_target != "self"`, not "column absent") — this pass found
  it fails safely by accident of a broad `except Exception`, not by a
  test-verified contract.
- **M4b should also decide what "queued forever" means for `business`-
  targeted missions** — right now a customer mission sits queued with no
  UI path to ever leave that state; that's correct for safety today but
  worth an explicit product decision before customers can trigger Execute.

## Known limitations

- This report reflects a single point-in-time snapshot (2026-07-10). All
  three schema gaps are expected to be resolved by founder action #1 above;
  once applied, several "could not verify" items in this report become
  verifiable and should be re-run.
- The live browser walkthrough used the seeded e2e business ("Seeded Demo
  Co"), not a fresh business created through signup/intake — consistent
  with the precedent set by `e2e/business-tabs.spec.ts` and other M-series
  verification passes.
- Console warnings unrelated to this batch were observed during the
  Operating Team tab render (React duplicate-key warning, key
  `idea_captured`, ~20 occurrences) — pre-existing, not caused by or fixed
  in this pass, logged here for visibility. Not investigated further as
  out of scope.
- Screenshots and raw response dumps are local artifacts only (gitignored,
  under `runner/langgraph/outbox/`, per this repo's convention that
  `outbox/` is transient and never committed):
  `01-dashboard.png`, `02-overview.png`, `02b-overview-full.png`,
  `03-actions-tab.png`, `03-before-execute.png`, `04-after-execute-click.png`,
  `04-after-execute-body.txt`, `05-approvals-panel.png`,
  `05-approvals-body.txt`, `06-operating-team-tab.png`,
  `06-operating-team-body.txt`, `10-overview-tall.png`,
  `11-execute-visible.png`, `12-after-execute.png`,
  `12-after-execute-body.txt`, `13-execute-error-fullscreen.png`,
  `execute-network-log.json`, `console-errors.json` — all under
  `runner/langgraph/outbox/m4a-10-screenshots/`.
