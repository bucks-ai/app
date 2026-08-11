# M4c Verification Report

**Mission:** M4c — Loop Babysitter & Continuous Operation
**Verification pass:** 2026-08-10
**Branch audited:** `main` at `bc3a998`

---

## Verdict

**M4c is code-complete and test-verified. The overnight acceptance test has not been run.**

This distinction matters and this report says so plainly per the founder's own
standard: *"If M4c ships and the founder is still hand-running `gh pr merge` or
editing runtime JSON, M4c has FAILED regardless of what its tests say."*

The 2,868-test suite covers all 13 failure modes. The overnight run — running a
real mission unattended from start to finish, measuring founder touch count — has
**not been executed** as of this report date. The code machinery is in place.
Whether it works in the real world on a real mission is a claim this report
cannot make. That gap is the most important fact in this document.

---

## 1. The 13 failure modes: code vs. live evidence

Each item below names the M4b incident, the code that addresses it, and what
is tested vs. what remains live-unverified.

---

### 1 — Unapplied migrations silently blocking startup

**M4b incident:** 6 pending migrations silently blocked startup on cycle 0 each
time the loop launched. `0006` then warned on every subsequent run without
resolving.

**Code:** `check_pending_migrations_if_needed` node in `graph.py:350–423`, fed by
`tools/environment_ownership.py` `apply_pending_migrations()`. When
`AUTO_APPLY_MIGRATIONS=true`, additive migrations that pass the existing
`sql_guard` scan are applied automatically. When false (the default), a loud
`migrations_pending` event fires regardless — it is no longer silent.

**Tests:** `tests/test_migrations_wiring_node.py` — **11 passed**. Covers:
no-op without DB, loud alert with filenames, auto-apply happy path, guard-blocked
file never auto-applied, non-additive file stops the apply sequence, node present
in graph and wired between launch-readiness and load-next-task.

**Live status:** `AUTO_APPLY_MIGRATIONS` has never fired in production (all six
live migrations in `_runner_migrations` carry the sentinel
`manual-apply-2026-07-22`). The code path is built and tested; it has never
been exercised by a real startup cycle.

**Residual risk:** `0006_deprecate_businesses_sandbox_config.sql` remains
un-applied in production. Impact is nil (only a `COMMENT ON COLUMN`), but the
ledger and migrations directory are out of sync. The automated warning would
surface this on the next run.

---

### 2 — Deployed app not matching `main` (Vercel not git-connected)

**M4b incident:** the Vercel project was not git-connected, so `main` merged for
hours while production served stale code. The founder debugged a "missing
feature" that had been in the repo the whole time.

**Code:** `environment_ownership.py` `verify_deployed_sha()` / `should_deploy()` /
`trigger_deploy_if_stale()`. When `AUTO_DEPLOY=true` and the deployed SHA does not
match `main`, the runner triggers a Vercel deploy before trusting the UI. Also
covers PostHog health probes post-deploy.

**Tests:** `tests/test_environment_ownership.py` — **32 passed** in full suite.
Covers: SHA pass/fail, auto-deploy trigger on failure, skip when token absent,
exception degradation. Does not cover a real Vercel API round-trip.

**Live status:** never fired against the production app. The SHA-check logic
requires the Vercel API to return a `deployment.meta.githubCommitSha` field —
not all deployment methods populate this. Behavior on a project that returns null
is untested in production.

---

### 3 — Repo and project provisioning

**M4b incident:** repos, Vercel projects, and git connections were founder-managed
checklists. No API call created or verified them.

**Code:** `tools/provisioning.py` — parent-child provisioning adapters for
GitHub (repos, scoped tokens), Vercel (projects, env vars, git connections),
Supabase (Management API), Stripe (Connect sub-accounts), Resend (domains,
sending keys), Twilio (subaccounts), PostHog (projects). Shipped in PRs #116
and #118.

**Tests:** `tests/test_provisioning.py` — **35 tests passed** in this suite.

**Live status:** no child resource has been created via these adapters in
production. The parent accounts exist; the provisioning API calls have never been
exercised against live vendor endpoints. For Stripe Connect, Resend, and Twilio
specifically: parent accounts do not yet exist, so the adapters can neither be
tested nor used until M4c's dependency batch-ahead surfaces those gaps.

---

### 4 — Config pre-validation at claim time (wrong repo name discovered late)

**M4b incident:** `testflow` vs. `testflow-demo` burned a full run and a
resource gate — the wrong repo name was discovered 40 minutes in via a `git
clone` failure rather than at claim time.

**Code — two layers:**

1. `tools/dispatch_preflight.py` `evaluate_loop_start()` — refuses to start from
   a non-`main` branch or a dirty working tree. Wired into `graph.py`
   `dispatch_preflight_node`.
2. `tools/repo_health_preflight.py` — before dispatching any worker into a
   workspace, verifies `check.sh` passes in the target repo so the worker cannot
   inherit a broken environment.

The specific "does this repo exist?" GET probe is **not implemented** as a
claim-time check. The dispatch preflight verifies the *local workspace remote*,
which means the wrong repo name would still consume one full `ensure_workspace`
clone attempt before the remote mismatch is caught.

**Tests:** `tests/test_dispatch_preflight.py` — **41 passed**; includes
wrong-remote abort, non-main refusal, dirty-tree refusal, prompt-as-instruction
not file-reference, business task dispatched with workspace cwd.
`tests/test_repo_health_preflight.py` — **12 passed**.

**Honest gap:** no pre-claim `GET /repos/{owner}/{repo}` probe at claim time.
Claim-gate validation confirms business config is present; it does not confirm
the configured repo is reachable before taking the task.

---

### 5 — Orphaned "running" tasks

**M4b incident:** FOUR tasks (m4b-07/08/09/10) stranded at `running` after
interrupted sessions. The existing requeue logic only handled `blocked`. On
restart, the loop saw zero `queued` work and exited `seeded_queue_exhausted`
— appearing done when it had stalled. Required hand-editing `.runtime/tasks.local.json`.

**Code:** `tools/state_self_healing.py` `run_startup_heal()`. On startup, requeues
any task stuck at `running` with no live worker/session owning it. Live owner is
verified by `psutil.pid_exists(owner_pid)` — if no live process holds the lock,
the task is requeued. After configurable max requeue attempts, parks the task at
`blocked` (not terminal `failed`) so it can be manually recovered without JSON editing.

`tools/task_schema.py` `load_tasks_with_repair()` — integrity check and auto-repair
on every load, covering stale retry windows, missing required fields, and
orphaned running tasks whose owner PID is gone.

**Tests:** `tests/test_state_self_healing.py` — **14 passed**. Includes: orphaned
running task requeued; live-owner task never stolen; unreachable DB requeues
instead of failing; endless-orphan parked at blocked not requeued forever.
`tests/test_task_queue_integrity.py` — **7 passed**. Covers load-with-repair at
the file level.

**Live status:** auto-repair fires on every startup. Has not been observed to
recover a real orphaned task under M4c (no mission has run under M4c yet).

---

### 6 — Git and PR autonomy

**M4b incident:** the founder personally ran `gh pr create`, `gh pr checks`,
and `gh pr merge` for every PR. A `main` divergence required manual rebase-vs-reset
decision. Six identical-formatting merge conflicts required manual resolution.
A stale `origin/main` produced a no-op merge.

**Code:** `tools/git_autonomy.py` — shipped in PR #100 (`6559c7e`). Provides:
- `sync_with_base()` — stash, fetch, rebase, restore. Detects when a local
  commit is already upstream and drops it cleanly.
- `wake_pr_for_checks()` — escalation ladder: `update-branch` API → rebase →
  merge-base → empty commit, in that order. Each rung is tried and its outcome
  logged before escalating.
- `resolve_trivial_conflicts()` — auto-resolves whitespace/formatting-only
  conflicts; escalates semantic conflicts.
- `protect_uncommitted_work()` — stash (including untracked files) before any
  checkout; restore on return. A failed stash blocks the checkout rather than
  risking the work.

**Tests:** `tests/test_git_autonomy.py` — **79 passed**. Includes: trivial
conflict auto-resolved; semantic conflict escalated; stash-before-checkout;
failed stash blocks checkout; rebase drops upstream commit; `wake_pr` ladder;
no destructive commands in sync path; real-git integration tests against a temp
repo.

**Honest gap:** the ladder has been exercised only in test repos. Real GitHub
PRs under M4c have not been opened, resolved, and merged autonomously. Any
edge case in GitHub's API behavior (rate limits, fork repos, required review
dismissal) is untested live.

---

### 7 — Never silently discard founder work

**M4b incident:** a worker's routine branch operation reverted uncommitted local
doc edits.

**Code:** `git_autonomy.protect_uncommitted_work()` called by `sync_with_base()`
and `safe_checkout()`. Stashes changes (including untracked) before any git
operation, restores afterward. If the stash pop fails, the stash is kept rather
than dropped. An `uncommitted_work_lost` event fires if any change cannot be
recovered — this reaches Slack.

**Tests:** `tests/test_git_autonomy.py` — covered in the 79-passed suite.
`test_protect_uncommitted_work_stashes_including_untracked`,
`test_failed_stash_blocks_the_checkout_rather_than_risking_the_work`,
`test_work_loss_events_reach_a_human`. Also `test_no_destructive_commands_anywhere_in_the_sync_path`.

**Scope-guard coverage:** `git_autonomy.path_in_scope()` refuses to auto-resolve
conflicts in files outside the task's declared scope. An out-of-scope conflict
is escalated to the founder even if it is trivially resolvable. This directly
addresses the M4b pattern of a task touching files it didn't declare.

---

### 8 — Idempotent seeding / duplicate seeding

**M4b incident:** "Execute: AI Infra" was seeded THREE times. 15 tasks with
colliding ids (`ai-infra-1..5` ×3) — sets disagreed on content. Required
hand-written dedupe script.

**Code:** `tools/mission_backlog.py` — the roadmap-as-data store. Auto-seeding
reads from the `mission_backlog` Supabase table (`approved=true`), checks for
existing local tasks for a `seeded_mission_id` before seeding, and enforces
globally-unique task ids. Reconciles against Supabase `mission_tasks` as source
of truth rather than blindly appending. Shipped PR #117.

**Tests:** `tests/test_mission_backlog.py` — covered in test suite.

**Live status:** the `mission_backlog` table has not yet been seeded with the
approved M4d→M9 roadmap. The founder has not yet approved the plan at the
backlog level. Auto-seeding has never fired in production — the M4c mission
itself was still seeded via the old SQL-editor method. The idempotency check
will be exercised on the first production auto-seed.

---

### 9 — Verify push destination for business tasks

**M4b incident:** business-mission commits must land in the business repo, never
the bucks-ai app repo. Worker summaries said "pushed to origin" without naming
the remote.

**Code:** `tools/environment_ownership.py` `verify_push_destination()` — asserts
the workspace remote matches the business's configured `repo_full_name` before
and after push. Hard-fails on mismatch. Also `tools/dispatch_preflight.py`
`verify_origin_remote()` — the pre-dispatch check that the workspace's `origin`
points at the business's repo. Returns the parsed `owner/name` without exposing
the credentialed URL.

**Tests:** `tests/test_environment_ownership.py` — `test_verify_push_destination_*`
(4 tests, passed). `tests/test_dispatch_preflight.py` — `test_verify_fails_when_remote_is_the_runners_own_repo` and related cases (41 passed).

**Live status:** the wrong-repo refusal guard from M4b (`foreign_repo_workspace.py
is_bucks_ai_repo()`) was already verified live in the M4b report. The new
`verify_push_destination` wrapper and the dispatch-time `verify_origin_remote`
check are tested but not yet exercised in a live business task execution.

---

### 10 — False completion (most dangerous bug class)

**M4b incident:** `ai-infra-03` was marked `complete` TWICE while the worker had
refused the task and deployed nothing. `deploy_result: null`, zero files created
or modified, worker's final output was a question. Silent false success is worse
than a crash.

**Code:** `tools/completion_evidence.py` — evidence-based completion gate
(`COMPLETION_EVIDENCE_GATE_ENABLED`, default **true**, no warn-only mode).

Two independent tests:
1. **Refusal/question/no-op detection** (`detect_refusal`): patterns "I'm not going
   to", "do you want me to", "Commit Result: skipped", zero created AND zero
   modified → marks `blocked`, never `complete`.
2. **Positive evidence** (`verify_evidence`): per task type — a file that exists on
   disk, a commit sha that exists in the remote, a deployment URL that returns 2xx.
   Evidence beats self-report in both directions.

Deployed in PR #104 (`efa6228`). No warn-only mode by design: the DoD gate had
one, defaulted to it, and that is exactly how `ai-infra-03` shipped twice.

**Tests:** `tests/test_completion_evidence.py` — **85 passed** in the M4c suite.
Covers: each refusal pattern, question pattern, no-op pattern, genuine completion
still passing, disabled gate restoring old behaviour, a business deploy task
requires deployment evidence, a bucks-ai deploy task falls back to artifact
evidence.

**Live status:** the gate wires into `graph.py` `update_task_status_node`. Never
been exercised in a live run where a worker actually refused — only in tests.

---

### 11 — Transient infra failure marked task terminally `failed`

**M4b incident:** degraded network broke Supabase lookup. Task marked `failed`
with "business not found." `failed` is terminal — every subsequent relaunch
exhausted in ~30s with nothing claimable. Hand-edit of `.runtime/tasks.local.json`
was the only recovery.

**Code:** `tools/failure_retry_backoff.py` — classifies errors as **transient**
(network/DNS/timeout/rate-limit/5xx → retry with exponential backoff, never
terminal) vs. **genuine** (the work is logically wrong → may be terminal, after
one retry). `tools/state_self_healing.py` `test_an_unreachable_database_requeues_the_task_instead_of_failing_it`.

The `fetch_business_by_id` retry (3 attempts, linear backoff) shipped 2026-07-31
as a partial mitigation — confirmed present at `tools/foreign_repo_workspace.py:183`.

**Tests:** `tests/test_state_self_healing.py` — `test_an_unreachable_database_requeues_the_task_instead_of_failing_it`, `test_a_network_failure_never_marks_a_task_terminally_failed`. `tests/test_failure_retry_backoff.py` — covered in full suite.

**Honest gap:** the general transient/genuine classification applies to the
recovery layer; the error classification at the *point of failure* (in the worker
or task-dispatch crash handler) still relies on the worker itself logging a
`structured_error` field. Workers that crash without a structured error are
classified conservatively (terminal after retries). Whether a network blip
during a live run correctly requeues vs. fails the task is untested in production.

---

### 12 — Business-task worker dispatch (root cause of M4b's deploy failure)

**M4b incident (marked ★ FIRST in the spec):** the runner wrote
`outbox/<task>_prompt.txt` and launched the worker with cwd in the bucks-ai tree
and the prompt as an `@<file>` reference. Both workers saw "a file describing a
deploy to someone else's Vercel project," correctly judged that irreversible, and
asked for clarification. Three deploy attempts. The workers behaved correctly;
the dispatch was broken. This blocked all unattended business execution.

**Code — two fixes, both in production:**

1. `workers/claude_worker.py:144–158` — prompt is passed via `stdin_data=prompt`
   (not as an argv file reference); `cwd=repo_path` is set from `task["repo_path"]`
   which `graph.py:_effective_repo_path()` resolves to the business workspace for
   `runner_target: "business"` tasks.

2. `tools/dispatch_preflight.py` `verify_origin_remote()` — before work begins,
   asserts the workspace's `origin` points at the business's repo. Hard-fail on
   mismatch, never returns the credentialed URL.

Shipped as PR #94 (`6f43ebd`, 2026-08-02).

**Tests:** `tests/test_dispatch_preflight.py` —
`test_claude_receives_prompt_as_instruction_not_file_reference`,
`test_business_task_dispatches_with_workspace_cwd`,
`test_self_task_dispatches_with_repo_path_cwd`,
`test_dispatch_cwd_is_never_none`,
`test_run_worker_prompt_passes_business_repo_path_through`. All passed.

**Live status:** no business task has been dispatched and executed under the
fixed dispatch path. The founder deployed testflow-demo manually on 2026-07-31
to close M4b. That step — the one that proves the full path — has not been
repeated under M4c with the fix in place.

---

### 13 — Escalation instead of diagnosis

**M4b incident:** when something broke, the founder got a symptom ("the loop
stopped") not a cause ("m4b-07 is stuck at running because its worker PID 14382
exited 2 hours ago and nothing requeued it").

**Code:** `tools/stop_diagnostics.py` — every loop stop logs:
- the stop reason, verbatim from state
- whether the stop reason's own numbers support it (catches the case where
  `consecutive_failures=3` fires when there was actually only 1)
- which task was in-flight
- how to resume

`tools/startup_preflight.py` — runs once at loop start, verifies all production
assumptions (env vars present, github token valid, vercel project reachable,
supabase connected), writes a human-readable report to `outbox/startup_preflight.txt`.

**Tests:** `tests/test_stop_diagnostics.py` — covered in full suite.

**Residual gap:** stop diagnostics are logged to Slack and to file. The
founder's visibility depends on Slack being open or reading the outbox files.
On a real overnight run, the diagnostic may exist but go unread until morning.
The phone push (ntfy.sh) only fires for credential requests — a loop stop from
a bug produces a Slack message, not a phone buzz. If the phone stays silent,
the founder may not know the loop stopped.

---

## 2. Features shipped but not in the 13

These M4c deliverables are in production and tested but derive from the mission
spec's supporting items rather than the 13 named failures.

| Feature | Location | Tests | Status |
|---|---|---|---|
| Loop watchdog (auto-restart) | `tools/loop_watchdog.py`, `main.py watchdog` cmd | `test_loop_watchdog.py` | Code-complete, unrun live |
| Limits-aware pause/resume | `graph.py` cooldown + `loop_watchdog.py` | `test_cooldown_*.py` | Code-complete |
| Heartbeat + stall detection | `loop_watchdog.py` `babysitter_heartbeat` event | `test_loop_watchdog.py` | Code-complete |
| Auto-approval routine gates | `tools/auto_approval.py` | `test_auto_approval.py` | Code-complete |
| Roadmap-as-data + auto-chaining | `tools/mission_backlog.py` | `test_mission_backlog.py` | Not yet seeded |
| Phone push (ntfy.sh) | `tools/ntfy_tools.py` | `test_ntfy_tools.py` | Configured (`NTFY_TOPIC=bucks-ai-runner-7x9k2m`); untested live |
| Dependency batch-ahead | `tools/dependency_batch_ahead.py` | `test_dependency_batch_ahead.py` | Code-complete |
| Parent-child provisioning | `tools/provisioning.py` | `test_provisioning.py` | Code-complete; no child resources created live |
| Overnight settings profile | `profiles/overnight.env` | `test_overnight_settings_profile.py` | Ready to copy |
| Doctrine ingestion | `tools/mission_backlog.py` `load_strategy_doc()` | `test_mission_backlog.py` | Wired; not exercised |
| Stop diagnostics | `tools/stop_diagnostics.py` | `test_stop_diagnostics.py` | Wired |

---

## 3. Test suite

| Suite | Result |
|---|---|
| Runner — `python -m pytest tests/ -q` (from `runner/langgraph/`) | **2,868 passed**, 0 failed |

Run on `main` at `bc3a998`, 2026-08-10. 931 `DeprecationWarning`s from `datetime.utcnow()`
in several tools — these are warnings, not failures, and are consistent with the
Python version in use. No logic is affected.

---

## 4. The acceptance test: not run

The M4c mission spec (`docs/M4C-MISSION-SPEC.md`) states the acceptance test for
m4c-10 plainly:

> *run a real mission overnight, unattended, and report exactly how many times the
> founder was touched and why. Target: zero touches except genuine new-credential
> requests.*

**This test has not been run.**

No overnight mission was executed under M4c. No founder touch count can be
reported. The following statements are therefore outside the bounds of what this
report can support:

- "The runner can execute a full business mission without founder involvement."
- "The phone buzzes zero times on a quiet night."
- "The loop survives usage limits and resumes."
- "Orphaned tasks are auto-recovered in a real run."

All of the above are plausible given the code that shipped. None of them are
*demonstrated*.

---

## 5. The founder's standard, applied plainly

The handoff (`CHAT_HANDOFF_2026-07-11.md`) records the standard verbatim:
*"it genuinely needs to be powerful."* The operationalisation: if M4c ships and
the founder is still hand-running `gh pr merge` or editing runtime JSON, M4c
has failed regardless of what its tests say.

Applying that standard to the current state:

**What would pass the standard:**
- A real business mission executes from task 1 to deployed product, overnight,
  with zero or one founder touch (only a genuine new-credential request).
- The founder wakes up to a Slack log showing PRs created, checks waited for,
  PRs merged, deploy triggered, completion verified — all by the runner.
- Runtime JSON is never opened.
- `gh pr merge` is never run by hand.

**What this report can say today:**
- The code that would produce that experience has been written and tested.
- Every M4b incident that blocked the previous session has a specific code fix
  with passing tests.
- No overnight run has validated it.

**Recommended immediate action:** run a real mission (M4d or the first M5
candidate) overnight, with `AUTO_MERGE=true`, `AUTO_APPLY_MIGRATIONS=true`,
and the `profiles/overnight.env` settings loaded. Record the founder touch count.
If it is zero or one (credential request only), M4c is done. If it is higher,
M4c is not done, and whatever caused the touches becomes the M4c follow-on list.

---

## 6. Known gaps not addressed by M4c

These items are recorded as outstanding, not as failures of M4c scope:

1. **No GET-probe of `repo_full_name` before claiming.** The wrong-repo bug can
   still cost one failed `ensure_workspace` attempt. Cheap to add; deferred.

2. **`mission_backlog` not yet seeded with M4d→M9 roadmap.** Auto-seeding and
   chaining are built but have nothing to chain to. The founder has not yet
   approved the plan at the backlog level.

3. **No live proof of ntfy phone push.** NTFY_TOPIC is configured. A credential-
   request event has not been generated live under M4c to confirm the phone
   buzzes.

4. **`0006` migration un-applied in production.** Zero impact; the ledger is out
   of sync with the directory. Apply via SQL editor or wait for `AUTO_APPLY_MIGRATIONS`
   to handle it on the next startup.

5. **`rls.integration.test.ts` is flaky in full-suite runs.** Documented in M4b
   report §6. Not fixed in this pass (a verification pass should not alter what
   it measures). Fails with `Hook timed out in 10000ms`; passes in isolation.
   The RLS cross-tenant denial guarantee is therefore not continuously enforced.

6. **Mission-level completion never closes.** Three M4b business missions are
   still `running` in the production `missions` table. A task completion closing
   its parent mission has not been implemented. This is not a M4c regression —
   it predates M4c — but it means the app UI shows perpetually in-progress
   missions.

7. **Structured error classification at dispatch-crash level.** Workers that crash
   without a structured `error_type` field are conservatively classified as
   terminal after retries. This is correct but conservative; a network blip in
   the Claude CLI layer would exhaust retries when it should backoff-and-requeue.

8. **Parent accounts for Stripe, Resend, Twilio do not yet exist.** The
   provisioning adapters are built but cannot create child resources without a
   parent account. The dependency batch-ahead will surface these when the first
   mission that needs them is seeded.

---

## 7. What could not be verified

Stated explicitly per the audit standard:

- **Any live overnight run.** Not executed. No touch count. No real-world proof.
- **Business task dispatch on the fixed path.** `workers/claude_worker.py` now
  dispatches via stdin with correct cwd; the last live business task run (M4b)
  used the broken path. The fix has not been exercised live.
- **Loop watchdog auto-restart.** The watchdog logic is tested; the `main.py watchdog`
  command has not been run for a multi-hour autonomous session.
- **ntfy phone push delivery.** Configured; never triggered in production.
- **Auto-seeding and mission chaining.** The `mission_backlog` table is empty.
  No mission has been seeded from it or chained from a previous completion.
- **Completion evidence gate blocking a real refusal.** The gate is wired; no
  real worker refusal has occurred under M4c to trigger it.
- **Auto-approval resolving a real PR merge gate.** `auto_approval.py` is wired;
  no real PR has been opened and auto-merged under M4c.
- **Transient-vs-genuine error classification in a live degraded-network run.**
  Tested; not exercised.

---

## 8. Known limitations of this report

- Point-in-time snapshot, 2026-08-10. Code-complete and tested; overnight run not run.
- All runner tests are against a local Python test environment, not against live
  GitHub, Vercel, Supabase, or ntfy endpoints (except the integration tests
  explicitly marked as such, which share the M4b report's caveat: they use the
  service-role key and bypass RLS).
- The M4b manual deploy is still the last live evidence that the runner touches a
  business repo. Until a live business task executes under the fixed dispatch, that
  single data point stands alone.
- This report does not re-read the full Claude/Codex worker transcripts from M4b.
  The dispatch root-cause is corroborated by the prompt artifact and two
  independent worker outputs, as documented in M4b report §1.3 and §8.

---

## 9. Recommended next step (M4d prerequisite)

**Run the overnight acceptance test before seeding M4d.**

1. Apply `profiles/overnight.env` settings (raise `AUTO_APPLY_MIGRATIONS=true`
   for this run, so `0006` is handled automatically).
2. Seed one small, well-specified mission into `mission_backlog` with `approved=true`.
3. Launch the watchdog: `python main.py watchdog`.
4. Wake up to the Slack log. Record every founder touch.
5. If touch count is 0–1 (credential request only): M4c is demonstrated. Seed M4d.
6. If touch count is higher: the additional touches become the M4c follow-on list.
   Fix them before seeding M4d — the mission spec's sequencing rule exists because
   compounding unseen failures is exactly how M4b consumed six hours.

The worst outcome is running M4d on an M4c that isn't actually working and
discovering it three sessions from now. The overnight run is cheap insurance.
