# Auto-Deploy Acceptance Smoke Note

**Date:** 2026-06-10
**Branch:** feature/runner-auto-deploy-acceptance-smoke
**Type:** docs

## Summary

This note validates the bucks.ai runner's `AUTO_DEPLOY` acceptance path: after a
worker task lands a commit and checks pass, the runner triggers a Vercel deploy,
polls it to a terminal state, and either continues the loop (READY) or halts it
(failed / timed out). The path is exercised end-to-end by the existing unit
suites — no live Vercel call is required to accept it.

## Acceptance Path

The deploy step runs as the `deploy_if_needed` LangGraph node (`graph.py:305`),
wired between `apply_sql_if_needed` and `update_github_if_needed`
(`graph.py:520-521`):

```
run_checks_if_needed
  → commit_push_merge_if_needed
  → apply_sql_if_needed
  → deploy_if_needed            ← AUTO_DEPLOY acceptance step
  → update_github_if_needed
  → update_logs_and_state
  → ask_chatgpt_next_task
  → decide_continue_or_stop
```

### Deploy gate

`deploy_if_needed` only triggers a deploy when **all** of these hold
(`graph.py:316`):

1. `worker_result.success` is true
2. `state.check_passed` is true
3. `state.last_commit` is set (a commit actually landed)

It then short-circuits with a logged `deploy_skipped` event if `AUTO_DEPLOY` is
off (`graph.py:323`) or no `VERCEL_TOKEN` is configured (`graph.py:330`).

### Deploy verdict

When the gate opens, `trigger_deploy` (`tools/vercel_tools.py:212`) reads the
latest deployment and, when `AUTO_DEPLOY_POLL` is on, calls
`poll_deployment_until_terminal` (`tools/vercel_tools.py:83`) to wait for a real
verdict instead of an in-progress snapshot. The poll loop normalizes Vercel's
`readyState`/`state` field and resolves to one of:

| Outcome | `ready` | `terminal` | `timed_out` | Loop effect |
|---------|---------|-----------|-------------|-------------|
| `READY` | true | true | false | continue |
| `ERROR` / `CANCELED` / `DELETED` | false | true | false | **block** (`deploy_failed`) |
| Poll budget exhausted | false | false | true | **block** (`deploy_timed_out`) |
| Vercel unreachable / poll disabled | false | false | false | continue (degraded) |

### Loop blocking

When `BLOCK_ON_DEPLOY_FAILURE` is on and the deploy is not ready
(`graph.py:357`), a polled terminal failure or a poll timeout sets
`state.stop_reason` to `deploy_failed` / `deploy_timed_out`. `decide_continue_or_stop`
(`graph.py:434`) then ends the run cleanly so the runner does not pile new tasks
on top of a broken deployment. A degraded/unavailable deploy (no token, API
unreachable, polling disabled) is **not** treated as a failure and the loop
continues.

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `AUTO_DEPLOY` | `true` | Trigger a Vercel deploy after a commit lands |
| `AUTO_DEPLOY_POLL` | `true` | Poll the deploy to a terminal state before reporting |
| `BLOCK_ON_DEPLOY_FAILURE` | `true` | Halt the loop on a failed/timed-out deploy |
| `VERCEL_POLL_TIMEOUT` | `180` | Seconds to wait for a terminal deploy state |
| `VERCEL_POLL_INTERVAL` | `5` | Seconds between deploy status polls |
| `VERCEL_TOKEN` | — | Required; absent → deploy skipped (degraded, non-blocking) |
| `VERCEL_PROJECT_ID` | — | Scopes the deploy status read to one project |

## Check Result

`./scripts/check.sh` — pass (Next.js lint + build; this branch only adds a docs
file, no app code changed).

Acceptance suites (`python tests/<name>.py`):

- `tests/test_deploy_node.py` — 15 passed, 0 failed
- `tests/test_vercel_polling.py` — 14 passed, 0 failed

These cover the happy path, deploy-failure / timeout loop-blocking, the
degraded (no-token / unreachable) non-blocking path, every skip guard, and the
node's wiring into the graph.

## Known Limitations

- Acceptance is validated against stubbed `trigger_deploy` / injected poll
  fetchers; no live Vercel deployment is created in this run. See
  `outbox/runner-auto-deploy-live-smoke_prompt.txt` for the live variant.
- `poll_deployment_until_terminal` without a `deployment_id` tracks the *latest*
  deployment for the project, which can race a just-pushed commit if Vercel has
  not yet registered the new build.
- Loop-blocking is decided from poll signals only; a deploy that Vercel reports
  as READY but is functionally broken still passes the gate.
