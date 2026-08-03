# M4c.0 — Gate Authority Audit

**Task:** every gate defers to the external authority — stop over-blocking
**Date:** 2026-08-02
**Code:** `runner/langgraph/tools/gate_authority.py` (registry + policy), `graph._record_gate_block` (application)

## Why

`poll_pr_checks` failed PR #94 because an advisory job named
`E2E (Playwright, Vercel preview) [informational]` reported failure — while all
five *required* checks were green. GitHub branch protection, the actual
authority on what blocks a merge, would have merged it. The runner was stricter
than the repo's own policy, and that single false failure exhausted m4c-01's
retries and killed the loop.

A fix for that specific case shipped as `PR_CHECKS_NON_BLOCKING`. This audit
generalises it into two rules that every gate now follows.

### Rule 1 — consult the authority, don't guess

Most gates re-implement a judgement something outside the runner already makes.
Where such an authority exists, the gate defers to it. The clearest failure of
this rule was the resource gate: during M2 and M4b it repeatedly halted the
whole run asking a human to provision `VERCEL_TOKEN` and `VERCEL_PROJECT_ID`
that were in `.env` the entire time. The runner's own config/env is the
authority on whether a credential exists — so the gate now checks there before
writing a request.

### Rule 2 — block proportionately

A gate that judges **this task** has no business stopping the other nine queued
tasks. A gate that judges **the run** legitimately stops everything. The default
is therefore skip-this-task-and-continue; a loop-wide halt is opt-in per gate
and must be justified by the gate assessing run-level state. This is enforced by
a test: `test_run_level_gates_are_loop_scoped` fails if any gate declares a
loop-wide halt while only assessing one task.

### Rule 3 — record who you consulted

Every gate that blocks now merges `authority_payload(...)` into its `log_event`
payload, so the flight recorder answers "on whose authority?" for every block:

```json
{"gate": "pr_checks", "authority": "github_branch_protection",
 "authority_external": true, "gate_assesses": "task", "block_scope": "task"}
```

## The audit

| Gate | External authority | Was | Now | Proportionality |
|---|---|---|---|---|
| **PR checks** | GitHub branch protection (required-checks list) | every check run treated as a merge gate; one advisory job killed the run | runs matching `PR_CHECKS_NON_BLOCKING` are reported via `pr_checks_advisory_failed`, never fatal | task — a red PR blocks its own merge |
| **Merge approval** | the human, via `inbox/<id>_merge_approved.txt` | `stop_reason=awaiting_merge_approval` → whole run stopped | task marked `blocked`, loop continues; approval file requeues it | task — a human approves one merge, not the run |
| **SQL approval** | the SQL guard (`sql_guard.scan_sql_text`) + `SQL_APPROVAL_POLICY` | already task-scoped: the SQL isn't applied, the loop isn't halted | unchanged; now records its authority | task — **non-additive SQL still blocks the apply** |
| **Resource / credential** | the runner's own config + env | trusted the worker's self-report; halted the run for credentials already in `.env` | names already present are filtered out before anything is written; remaining gaps block the task only | task — one missing credential ≠ ten blocked tasks |
| **Acceptance criteria** | the task record itself | strict mode stopped the run | task marked `failed`, loop continues | task — one under-specified task says nothing about the next |
| **Definition of done** | `check.sh` / CI | strict mode stopped the run | task marked `failed`, loop continues | task — a second opinion on one task's output |
| **Independent code review** | CI + branch protection | strict mode stopped the run | task marked `failed`, loop continues | task — a rejected diff blocks its own merge |
| **High-risk review** | the Claude review verdict | strict mode stopped the run | task marked `failed`, loop continues | task — one diff, and the model can be wrong |
| **Strategic** | the human, via `inbox/strategic_review_N_approved.txt` | stopped the run | **unchanged — still stops the run** | run — a whole-run pause is the entire point of the gate |
| **Cost budget (session)** | `MAX_SESSION_COST_DOLLARS` | stopped the run | **unchanged — still stops the run** | run — spend is irreversible and the cap is run-level |
| **Cost budget (task)** | `MAX_TASK_COST_DOLLARS` | stopped the run | recorded, loop continues | task — the task already ran and paid; the session cap catches runaway spend |
| **Worker timeout** | the worker process itself | stopped the run | **unchanged** | run — only fires after `MAX_WORKER_TIMEOUTS` across the session |
| **Stale run** | wall clock | stopped the run | **unchanged** | run — a wedged loop is a property of the run |
| **Repeated error / task** | session error history | stopped the run | **unchanged** | run — the same error across tasks is systemic by definition |
| **Codex usage limit** | the provider's response | stopped the run | **unchanged** | run — the provider rate-limits the account, so every task is affected |
| **Worker health** | the worker health probe | stopped the run | **unchanged** | run — an unusable worker binary blocks every task equally |
| **Deploy** | Vercel deployment status | stopped the run (opt-out via `BLOCK_ON_DEPLOY_FAILURE`) | **unchanged** | run — a broken production deploy makes further merges unsafe |
| **Launch readiness** | the readiness scorecard | stopped the run | **unchanged** | run — a pre-flight check of the environment, before any task starts |

Nine gates changed behaviour; nine were already proportionate and only gained
authority recording.

## What was deliberately *not* weakened

- **Non-additive SQL** — `sql_guard` still refuses to apply it. Approval gating
  is scoped to the apply, not the loop, and was never the over-blocking problem.
- **Spend past the session cap** — irreversible, run-level, still halts.
- **Irreversible operations** — the deploy gate, rollback/revert policy, branch
  protection, and the protected-branch rewrite in `load_next_task` are untouched.

`gate_authority.evaluate_gate_block` only ever *widens* a gate's declared scope
(via `systemic=True` or `GATE_BLOCK_SCOPE=loop`); it can never narrow one. So no
policy value can downgrade a destructive gate's block into a skip, and
`test_destructive_gates_are_never_downgraded` asserts it.

## Consequences of skip-and-continue

Letting the loop survive a gate block required three supporting fixes, each of
which would otherwise have turned an over-block into a worse failure:

1. **Per-task state must be reset** (`graph._reset_task_scoped_state`). Before
   M4c.0 a pending/failed verdict always ended the run, so it could never leak
   into the next task. Now it would: task A's `resource_request_status="pending"`
   would route every subsequent task straight back out of the graph without
   dispatching a worker. `load_next_task` now clears the previous task's
   verdicts. Session counters are deliberately untouched.
2. **A skipped task must still count as a loop.** Task-scoped blocks
   short-circuit to `decide_continue_or_stop` and never reach
   `update_logs_and_state`, so `_record_gate_block` bumps `loop_count` and
   `last_task_completed_at` itself — otherwise a run of skips would respect
   neither `MAX_LOOP_TASKS` nor the stale-run watchdog.
3. **An unblock signal is consumed once.** A task that blocks again for the same
   reason after being requeued would previously have stopped the run; now it
   would be requeued, re-run and re-blocked forever. `unblock_requeued_at` caps
   it at one attempt per signal.

The merge-approval gate now marks its task `blocked` (it previously relied on
`stop_reason` to halt), and `requeue_fulfilled_blocked_tasks` learned to accept
`<id>_merge_approved.txt` as an unblock signal so approved merges resume.

## Configuration

| Env var | Default | Effect |
|---|---|---|
| `GATE_BLOCK_SCOPE` | `proportionate` | `proportionate` honours each gate's declared scope. `loop` restores the pre-M4c.0 behaviour where every gate block stops the run — a single-switch rollback. |
| `PR_CHECKS_NON_BLOCKING` | `[informational]` | Case-insensitive substrings; matching check runs are advisory. |

## New events

| Event | Meaning |
|---|---|
| `gate_blocked` | A task-judging gate (acceptance criteria, DoD, code review, high-risk review) rejected its task. |
| `gate_block_task_scoped` | A block was applied to one task only; carries `would_have_stopped_with`, the `stop_reason` the pre-M4c.0 runner would have used. |
| `resource_request_already_satisfied` | The worker asked for credentials the runner already holds; names only, never values. |

Every blocking event now also carries `gate`, `authority`, `authority_external`,
`gate_assesses`, and `block_scope`.

## Known limitations

- Credential matching is name-based: `VERCEL_TOKEN` present in env satisfies a
  request for `VERCEL_TOKEN` even if the token lacks the required scope. The
  worker will then fail on the real API error, which is the more actionable
  signal than a human-provisioning request for something already provisioned.
- A requeued task re-runs from the start, so a merge approved after the fact
  costs one extra worker dispatch. This matches the pre-existing resource-gate
  behaviour rather than introducing a new one.
- `business_repo_forbidden` / `business_not_found` /
  `business_repo_remote_mismatch` still halt the run. They are security and
  configuration violations rather than gates, and were left alone deliberately;
  applying the same proportionality reasoning to them is follow-up work.
