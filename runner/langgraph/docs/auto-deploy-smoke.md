# Auto-Deploy Smoke Test

**Date:** 2026-06-10
**Branch:** feature/runner-auto-deploy-smoke
**Worker:** claude (outbox mode)

## Summary

This note confirms that the bucks.ai runner's auto-deploy flow works correctly:
after a worker task commits successfully and checks pass, the `deploy_if_needed`
node triggers a Vercel deploy and **polls it to a terminal state** (READY /
ERROR / CANCELED) instead of reporting an in-progress snapshot. A failed or
timed-out deploy halts the loop so the runner doesn't pile new tasks on top of a
broken deployment.

## Auto-Deploy Flow

The `deploy_if_needed` node (`graph.py:301`) runs after
`commit_push_merge_if_needed` and `apply_sql_if_needed`, before
`update_github_if_needed`:

1. **Gate** — deploy only when the worker succeeded, `check_passed` is true, and
   a commit landed (`state.last_commit`). Otherwise emit `deploy_skipped`.
2. **Config gates** — skip with `deploy_skipped` when `AUTO_DEPLOY=false` or no
   `VERCEL_TOKEN` is configured (degraded, not a failure).
3. **Trigger + poll** — call `trigger_deploy(project_id=cfg.vercel_project_id)`,
   which reads the latest deployment and, when `AUTO_DEPLOY_POLL=true`, calls
   `poll_deployment_until_terminal` until READY / ERROR / CANCELED or
   `VERCEL_POLL_TIMEOUT` elapses.
4. **Record verdict** — set `state.deploy_result` and `state.deploy_ready`, and
   emit a `deploy_result` event (success, ready, state, timed_out, polls,
   elapsed).
5. **Block on failure** — when `BLOCK_ON_DEPLOY_FAILURE=true` and the polled
   deploy failed (terminal, not ready) or timed out, set `stop_reason`
   (`deploy_failed` / `deploy_timed_out`) and emit `loop_blocked_on_deploy`.
   `decide_continue_or_stop` then ends the run cleanly, and
   `ask_chatgpt_next_task` early-returns so the planner isn't asked for a task
   that would never run.

A degraded/unavailable deploy (no token, API unreachable, polling disabled) is
**not** treated as a failure — the loop continues.

## Polling Tool

`poll_deployment_until_terminal` (`tools/vercel_tools.py:83`) resolves the
deployment by id (or tracks the latest for a project), then loops:

- `normalize_ready_state` accepts either `readyState` or `state` from Vercel.
- `is_terminal_state` returns true for `READY` and the failed set
  (`ERROR`, `CANCELED`, `DELETED`).
- It only sleeps for another round if there is time left before `timeout`,
  emitting `deploy_poll_*` events each tick.

`fetch` / `sleep` / `now` are injectable so the loop is unit-testable with no
network or real time.

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `AUTO_DEPLOY` | `true` | Trigger a Vercel deploy after commit/merge |
| `AUTO_DEPLOY_POLL` | `true` | Poll the deploy to a terminal state |
| `BLOCK_ON_DEPLOY_FAILURE` | `true` | Halt the loop on a failed/timed-out deploy |
| `VERCEL_POLL_TIMEOUT` | `180` | Max seconds to wait for a terminal state |
| `VERCEL_POLL_INTERVAL` | `5` | Seconds between status reads |
| `VERCEL_PROJECT_ID` | _(unset)_ | Scope deploy polling to one project |

## Events Emitted

`deploy_skipped`, `deploy_started`, `deploy_poll_started`, `deploy_poll_tick`,
`deploy_poll_ready`, `deploy_poll_failed`, `deploy_poll_timeout`,
`deploy_poll_unavailable`, `deploy_result`, `deploy_completed`,
`loop_blocked_on_deploy`, `vercel_degraded`.

## Smoke Verification

The auto-deploy path is covered end-to-end by two standalone suites (no network,
no disk I/O — `trigger_deploy`, `log_event`, and state persistence are stubbed):

```
$ .venv/bin/python tests/test_deploy_node.py
15 passed, 0 failed

$ .venv/bin/python tests/test_vercel_polling.py
14 passed, 0 failed
```

These exercise the happy path (deploy runs when changes land, reports READY),
the loop-blocking paths (failure / timeout set `stop_reason`; ready / flag-off /
unavailable do not), every skip gate (no commit, check failed, worker failed,
`AUTO_DEPLOY` off, no token), project-id passthrough, graph wiring, and the
poller's terminal/timeout/unavailable branches.

## Check Result

`./scripts/check.sh` — pass

## Known Limitations

- The smoke test exercises the node and poller logic with stubbed Vercel
  responses; it does not perform a live deploy against the Vercel API.
- `trigger_deploy` reads the latest deployment rather than creating a new one —
  it relies on Vercel's Git integration to start the build on push.
- Polling tracks the latest deployment for a project; without `VERCEL_PROJECT_ID`
  set, a busy account could surface an unrelated deployment as "latest".
