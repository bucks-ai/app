# Two-Worker Claude Smoke Test

**Date:** 2026-06-07
**Branch:** feature/runner-two-worker-claude-smoke
**Worker:** claude (outbox mode)

## Summary

This note confirms that the bucks.ai runner successfully dispatched a backend task
to the Claude worker via the outbox mechanism and received a completed response.

## Worker Routing

The runner selects workers based on task type:

| Task type | Worker |
|-----------|--------|
| `ui`, `frontend`, `polish`, `design` | Codex |
| `backend`, `api`, `schema`, `agent`, everything else | Claude |

This task (`type: backend`) was correctly routed to the Claude worker.

## Dispatch Mode

Claude CLI (`claude`) was detected on PATH. The worker wrote the prompt to
`outbox/runner-two-worker-claude-smoke_prompt.txt` and invoked Claude Code with
`--dangerously-skip-permissions` to complete the task autonomously.

## Two-Worker Configuration

Both workers are active and independently reachable:

- **Claude** (`workers/claude_worker.py`) — handles backend, API, schema, agent tasks
- **Codex** (`workers/codex_worker.py`) — handles UI, frontend, polish, design tasks

Worker selection happens in the `choose_worker` LangGraph node. No shared state
or locks exist between workers — each task is dispatched to exactly one worker
per loop cycle.

## Check Result

`./scripts/check.sh` — pass

## Known Limitations

- Only one worker is active per loop cycle; true parallel dispatch is not yet implemented.
- Outbox mode requires polling `inbox/<task_id>_response.txt`; timeout is 10 seconds in non-CLI mode.
