# Auto-Deploy Live Smoke Note

**Date:** 2026-06-10
**Branch:** feature/runner-auto-deploy-live-smoke
**Mode:** live (real Vercel API, real `VERCEL_TOKEN`)

## Summary

This note records a **live** smoke test of the runner's Vercel auto-deploy path. Unlike
`tests/test_vercel_polling.py` and `tests/test_deploy_node.py`, which inject `fetch`/`sleep`/`now`
and never touch the network, this run exercised `tools/vercel_tools.py` against the **real**
Vercel API using the configured token. It confirms that `get_deployment_status` and
`poll_deployment_until_terminal` resolve a real deployment, normalize its `readyState`, and
return a correct terminal verdict.

## Live Results

| Step | Call | Result |
|------|------|--------|
| Status read | `get_deployment_status()` | `available=True` |
| Latest deployment | — | `bucks-ai-app-archive` (`dpl_3RF3SNHwDGudpD96aCis3e2hMbei`) |
| State normalize | `normalize_ready_state(latest)` | `READY` |
| Terminal check | `is_terminal_state("READY")` | `True` |
| Poll-to-terminal | `poll_deployment_until_terminal(timeout=30, interval=5)` | `ready=True, terminal=True, timed_out=False, polls=1, elapsed≈0.5s` |

The latest deployment was already `READY`, so polling returned a terminal verdict on the first
read without sleeping. The verdict shape matches what `trigger_deploy` and the
`deploy_if_needed` graph node consume (`success = bool(verdict["ready"])`).

## Live Config Observed

| Setting | Value | Notes |
|---------|-------|-------|
| `has_vercel` | `True` | `VERCEL_TOKEN` present in `.env` |
| `VERCEL_PROJECT_ID` | unset | Polling falls back to the latest deployment across the account |
| `AUTO_DEPLOY` | `True` | Deploy step active |
| `AUTO_DEPLOY_POLL` | `True` | Runner waits for a terminal state |
| `BLOCK_ON_DEPLOY_FAILURE` | `True` | Failed/timed-out deploy halts the loop |
| `VERCEL_POLL_TIMEOUT` | `180s` | Default |
| `VERCEL_POLL_INTERVAL` | `5s` | Default |

## Deploy Flow Under Test

`deploy_if_needed` (graph.py:301) runs after `apply_sql_if_needed` and only deploys when the
worker succeeded, checks passed, and a commit landed:

1. Skip cleanly if nothing was committed, `AUTO_DEPLOY=false`, or no `VERCEL_TOKEN`.
2. `trigger_deploy(project_id=cfg.vercel_project_id)` reads the latest deployment and, when
   `AUTO_DEPLOY_POLL=true`, calls `poll_deployment_until_terminal` to wait for READY vs
   failed/timed-out.
3. `state.deploy_ready = bool(deploy["success"])`.
4. If `BLOCK_ON_DEPLOY_FAILURE=true` and the deploy reached Vercel but failed or timed out,
   `loop_blocked_on_deploy` fires and the loop stops so new tasks don't pile on a broken deploy.
   A degraded/unavailable deploy (no token, API unreachable, polling disabled) is *not* treated
   as a failure and lets the loop continue.

## Check Result

- Unit tests (standalone, no pytest):
  - `python tests/test_vercel_polling.py` — 14 passed, 0 failed
  - `python tests/test_deploy_node.py` — 15 passed, 0 failed
- Live API smoke — pass (see Live Results above)

## Known Limitations

- `VERCEL_PROJECT_ID` is unset in `.env`, so the live read tracks the **latest deployment across
  the account** rather than a specific project. Set `VERCEL_PROJECT_ID` to scope polling.
- The latest deployment was already `READY`, so the in-progress polling loop
  (`QUEUED`/`BUILDING` → `READY`) and the timeout path were not exercised live; both remain
  covered by the injected-`fetch` unit tests.
- This smoke does not *trigger* a new deployment — `trigger_deploy` reads/polls the existing
  latest deployment rather than creating one (Vercel deploys are driven by the git push, not by
  this runner). A failed-deploy live verdict was therefore not observed.
- `pytest` is not installed in `.venv`; tests are run standalone as documented in their headers.
