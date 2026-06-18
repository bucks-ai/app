# Final LangGraph Validation Batch

Date: 2026-06-18
Branch: `feature/runner-final-validation-batch`
Task: `runner-final-validation-batch`

## Scope

This validation reviewed the recent LangGraph runner sequence and guard events
from local runner evidence. It is documentation/test-only. No app UI, backend app
routes, Supabase SQL, package files, or production behavior were changed.

Evidence sources:

- `runner/langgraph/logs/runs.jsonl`
- `runner/langgraph/.runtime/state.local.json`
- `runner/langgraph/.runtime/tasks.local.json`
- recent git history on `main`
- `runner/langgraph/docs/five-task-validation-batch.md`

## Current Local Runner Configuration

The local runner configuration observed during this validation is conservative:

| Setting | Observed value |
| --- | --- |
| `RUNNER_MODE` | `browser_or_cli` |
| `MAX_LOOP_TASKS` | `1` |
| `MAX_RUNTIME_MINUTES` | `180` |
| `AUTO_MERGE` | `true` |
| `AUTO_DEPLOY` | `true` |
| `AUTO_DEPLOY_POLL` | `true` |
| `BLOCK_ON_DEPLOY_FAILURE` | `true` |
| `AUTO_APPLY_SQL` | `true` |

Because `MAX_LOOP_TASKS=1`, the strongest evidence is from repeated single-task
runner executions, not from one uninterrupted long autonomous loop.

## Validation Evidence

| Capability | Evidence |
| --- | --- |
| Run summaries | `run_summary_digest` events were captured for successful and failed tasks, including `runner-codex-limit-notification`, `runner-branch-cleanup`, `runner-rollback-revert-policy`, `runner-model-routing-policy`, `runner-context-compression`, and `runner-five-task-validation-batch`. |
| Model routing | Commit `312e500` added model routing policy coverage; later `model_resolved` events selected `gpt-4o` for Codex tasks including `runner-context-compression`, `runner-five-task-validation-batch`, and this task. |
| Context compression | Commit `d590883` added deterministic compression utilities and tests; `runner-five-task-validation-batch` logged `context_compressed` after worker summary capture. |
| Branch cleanup | Commit `91f97bf` added cleanup support; `branch_cleanup_completed` events show local and remote deletion for `feature/runner-model-routing-policy`, `feature/runner-context-compression`, and `feature/runner-five-task-validation-batch`. |
| Rollback/revert policy | Commit `82690d1` added rollback/revert policy support and tests. The validation window confirms timeout failures skip deploy and schedule retry rather than proceeding to deploy. |
| Codex usage limit handling | Commit `fa44458` added usage-limit detection and notification tests. No live Codex limit was tripped in the final observed sequence. |
| GitHub task sync | Commit `c46be80` added GitHub issue/task sync improvements; `github_issue_sync` events are present in the validation window. |
| Deploy polling | Successful merged tasks logged `deploy_poll_started`, one `deploy_poll_tick`, `deploy_poll_ready`, and `deploy_result` with `state=READY`, including the five-task validation report run. |
| Timeout guard | `runner-rollback-revert-policy` timed out after the worker run, logged `worker_timeout_detected`, skipped deploy, and scheduled retry. |
| Failure retry guard | Failed or timed-out worker outcomes were converted into retry scheduling, including `runner-rollback-revert-policy`. |
| Cost guard | Commit `ef6d562` added cost and budget tracking guard tests. The final observed sequence did not trip the cost stop condition. |
| SQL scan path | A `sql_scan_passed` event was observed for an earlier `runner-branch-cleanup` failure path. This final validation introduced no SQL. |

## Recent Runner Commits Reviewed

| Commit | Purpose |
| --- | --- |
| `6e8d224` | Added the five-task runner validation report. |
| `d590883` | Added context compression utilities and tests. |
| `312e500` | Added model routing policy and tests. |
| `82690d1` | Added rollback/revert policy and tests. |
| `91f97bf` | Added branch cleanup support and tests. |
| `fa44458` | Added Codex usage-limit detection and tests. |
| `c46be80` | Added GitHub task sync improvements and tests. |
| `ef6d562` | Added cost and budget tracking guard and tests. |
| `53804e1` | Added worker timeout guard and tests. |
| `2f10059` | Added failure and retry guard and tests. |

## Recommended MAX_LOOP_TASKS Settings

| Mission size | Recommendation |
| --- | --- |
| 10 tasks | Reasonable next validation target. Use `MAX_LOOP_TASKS=10`, keep tasks documentation/test-only, set explicit task branches, and review the full event sequence afterward. |
| 25 tasks | Conditional. Run only after a clean 10-task validation with no unresolved retries, parse errors, deploy failures, or resource gates. Prefer `AUTO_APPLY_SQL=false` unless the queue explicitly validates SQL behavior in a disposable environment. |
| 100+ tasks | Not ready for unattended operation. Require strategic checkpoints, cost ceilings, dedicated external-service quotas, reliable planner JSON output, and a resumable incident protocol before attempting this scale. |

## Safe Worker Routing Guidance

- Route UI, frontend, design, and polish tasks to Codex on feature branches.
- Route backend, runner, schema, integration, and policy tasks to Claude unless
  there is a specific Codex-only reason.
- Keep all generated task branches in `feature/<task-id>` form.
- Keep `BLOCK_ON_DEPLOY_FAILURE=true` for any run that can deploy.
- For larger validation queues, prefer `AUTO_APPLY_SQL=false` unless the task
  explicitly validates SQL application and the database target is disposable or
  approved.
- Seed validation queues with explicit task objects rather than relying on
  planner-generated follow-up tasks for long runs.

## Go / No-Go Recommendation

Go for a controlled 10-task validation batch.

No-go for a 25-task or 100+ task unattended mission today. The runner has enough
guard coverage to proceed to a larger controlled validation, but the current
evidence still comes from repeated single-task runs. The next milestone should
prove one continuous 10-task loop with expected check, merge, cleanup, deploy,
summary, retry, and stop events.

## Remaining Limitations

- The final evidence is still dominated by sequential `MAX_LOOP_TASKS=1` runs.
- Planner output has produced parse errors in the recent log window; long runs
  should use a seeded queue or stricter planner output validation.
- The Codex usage-limit guard is covered by tests and implementation evidence,
  but no live final-sequence usage-limit stop occurred.
- The cost guard is covered by tests and implementation evidence, but no live
  final-sequence budget stop occurred.
- Deploy polling reached `READY`, but this validation did not inspect deployed
  application behavior.
- `AUTO_APPLY_SQL=true` was observed locally; this is risky for broad autonomous
  runs unless the SQL scanner and target database have been explicitly approved.

## Next Task

Run a seeded 10-task validation queue with `MAX_LOOP_TASKS=10`,
`AUTO_APPLY_SQL=false`, explicit `feature/<task-id>` branches, and a post-run
report that compares expected versus observed guard events for each task.
