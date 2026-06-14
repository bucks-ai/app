# bucks.ai Autonomous Development Runner

A self-directing development loop powered by LangGraph, ChatGPT (planner), Claude Code, and Codex (workers), with GitHub, Supabase, and Vercel integrations.

---

## Architecture

```
ChatGPT (planner)
      │ decides next task
      ▼
LangGraph loop controller
      │
      ├── Claude Code (backend / API / schema / agent tasks)
      └── Codex       (UI / frontend / polish tasks)
            │
            ├── GitHub (branch / commit / push / merge / issues)
            ├── Supabase (SQL scan → apply)
            └── Vercel (deploy status / trigger)
```

**Flight recorder:** `logs/runs.jsonl`
**Loop state:** `.runtime/state.local.json` (local only, gitignored)
**Task queue:** `.runtime/tasks.local.json` (local only, gitignored)

---

## Branch Safety

> **All generated tasks must operate on a feature branch — never on a protected branch.**

- Task `branch` field must always follow the pattern `feature/<task-id>` (e.g. `feature/operating-team-ui`).
- The runner creates the branch, commits worker output to it, and merges back to `main` only after `check.sh` passes.
- **Early guard (load_next_task):** If a task's `branch` field is set to a protected branch name (`main`, `master`, `dev`, `develop`, `production`, `release`), the runner rewrites it to `feature/<task-id>` before any worker prompt is generated. The rewritten branch is immediately persisted back to `.runtime/tasks.local.json` so the queue reflects the correct branch name. Two log events are emitted: `branch_rewritten` (before persist) and `branch_rewrite_persisted` (after persist).
- **Late guard (commit_push_merge_if_needed):** As a backstop, the runner also refuses to commit/push/merge to any protected branch and logs an `error` event. Reaching this guard indicates a misconfiguration — the early guard should have already corrected the branch.
- `AUTO_APPLY_SQL` should remain `false` until the SQL scanner (`sql_guard.py`) has been validated against your schema — unexpected migrations on `main` are irreversible.

---

## Roles

| Component | Role |
|-----------|------|
| ChatGPT | Planner — decides the next task, receives worker summaries |
| LangGraph | Loop controller — routes tasks, sequences steps, manages state |
| Claude Code | Worker — backend, API, schema, agent system tasks |
| Codex | Worker — UI, frontend, polish, design tasks |
| GitHub | Branch/commit/push/merge/issue tracking |
| Supabase | SQL scan and apply target |
| Vercel | Deployment target |

---

## Setup

```bash
cd runner/langgraph
cp .env.example .env
# Fill in your keys in .env
source .venv/bin/activate
python main.py setup
```

If Playwright browser automation is needed:
```bash
python -m playwright install
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required for |
|----------|-------------|
| `OPENAI_API_KEY` | ChatGPT planner (auto mode) |
| `ANTHROPIC_API_KEY` | Claude API (optional — Claude CLI preferred) |
| `GITHUB_TOKEN` | GitHub issues/PR integration |
| `SUPABASE_URL` | Supabase SQL execution |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase SQL execution |
| `VERCEL_TOKEN` | Deploy status / trigger |
| `VERCEL_PROJECT_ID` | Scope deploy polling to one Vercel project (optional) |
| `SLACK_WEBHOOK_URL` | Slack notifications for notable runner events (optional) |
| `SLACK_NOTIFY` | Enable/disable Slack notifications (default: true) |
| `SLACK_NOTIFY_EVENTS` | Comma-separated event types to notify on (default: curated set) |
| `BUCKS_AI_REPO_PATH` | Path to repo (default: `/home/arnavt/bucks-ai`) |
| `RUNNER_MODE` | `browser_or_cli` (default) |
| `MAX_LOOP_TASKS` | Max tasks per run (default: 10) |
| `MAX_RUNTIME_MINUTES` | Max runtime (default: 480) |
| `AUTO_MERGE` | Auto-merge on check pass (default: true) |
| `AUTO_DEPLOY` | Auto-trigger Vercel (default: true) |
| `AUTO_DEPLOY_POLL` | Poll the triggered deployment until it finishes (default: true) |
| `BLOCK_ON_DEPLOY_FAILURE` | Stop the loop when a polled deploy fails or times out (default: true) |
| `VERCEL_POLL_TIMEOUT` | Max seconds to poll a deployment before giving up (default: 180) |
| `VERCEL_POLL_INTERVAL` | Seconds between deployment status reads (default: 5) |
| `AUTO_APPLY_SQL` | Auto-apply scanned SQL (default: true) — **keep false until SQL parsing is verified** |
| `RESOURCE_GATE` | Pause the loop when a worker reports it needs a missing credential/resource (default: true) |
| `FAILURE_GUARD` | Retry failed tasks and stop the loop on repeated failures (default: true) |
| `MAX_TASK_RETRIES` | Times a failed task is requeued before giving up (default: 1) |
| `MAX_CONSECUTIVE_FAILURES` | Consecutive failures that trip the circuit breaker and halt the loop (default: 3) |

---

## CLI Commands

```bash
python main.py setup           # Validate config, create folders/files
python main.py status          # Print current .runtime/state.local.json
python main.py next-task       # Print next queued task
python main.py run-once        # Run one full LangGraph cycle
python main.py run-loop        # Run continuous autonomous loop
python main.py scan-sql path/to/file.sql   # Scan SQL file for dangerous statements
python main.py logs --tail 50  # Print last 50 log events
```

---

## Running the Loop

```bash
cd runner/langgraph
source .venv/bin/activate
python main.py setup
python main.py run-loop
```

---

## Task Queue

Tasks are stored in `.runtime/tasks.local.json` (gitignored, local only). Add tasks manually or let ChatGPT generate them:

```json
[
  {
    "id": "my-task",
    "title": "Build something",
    "type": "ui",
    "preferred_worker": "codex",
    "branch": "feature/my-task",
    "status": "queued"
  }
]
```

Task types: `ui`, `frontend`, `polish`, and `design` route to Codex. Everything else routes to Claude.

Codex UI tasks should always use feature branches so UI work can be checked before it reaches `main`.

> **Branch safety rule:** Tasks must **never** set `"branch": "main"`. Every task must use a feature branch in the form `feature/<task-id>`. The runner will create, push, and merge this branch automatically — writing to `main` directly bypasses all safety checks and will corrupt the loop state.

On first run, the runner migrates any existing `tasks.json` to `.runtime/tasks.local.json` automatically.

---

## logs/runs.jsonl

Append-only JSONL flight recorder. Each line is a JSON event:

```json
{"event_type": "task_loaded", "timestamp": "...", "task_id": "...", "payload": {...}}
```

Event types: `task_started`, `task_loaded`, `branch_rewritten`, `branch_rewrite_persisted`, `prompt_generated`, `planner_started`, `planner_finished`, `worker_started`, `worker_finished`, `summary_captured`, `run_summary_digest`, `check_started`, `check_passed`, `check_failed`, `branch_created`, `commit_created`, `push_completed`, `merge_started`, `merge_completed`, `deploy_skipped`, `deploy_started`, `deploy_completed`, `deploy_result`, `deploy_poll_started`, `deploy_poll_tick`, `deploy_poll_ready`, `deploy_poll_failed`, `deploy_poll_timeout`, `deploy_poll_unavailable`, `loop_blocked_on_deploy`, `sql_detected`, `sql_scan_passed`, `sql_scan_blocked`, `sql_applied`, `resource_request_pending`, `resource_request_waiting`, `resource_request_fulfilled`, `next_task_requested`, `loop_stopped`, `slack_degraded`, `error`

---

## .runtime/state.local.json

Current loop state, updated after every node. Stored in `.runtime/state.local.json` (gitignored). Safe to inspect mid-run:

```json
{
  "status": "running",
  "current_task_id": "operating-team-ui",
  "current_worker": "codex",
  "loop_count": 3,
  "worker_summary_digest": "Task: ...\nFiles: ...\nCheck: pass",
  ...
}
```

On first run, the runner migrates any existing `state.json` to `.runtime/state.local.json` automatically.

---

## Worker Modes

Each worker (Claude, Codex) operates in three modes:

1. **CLI mode** — if `claude` or `codex` CLI is on PATH, sends prompt directly.
2. **Outbox mode** — writes prompt to `outbox/<task_id>_prompt.txt`, waits for response in `inbox/<task_id>_response.txt`.
3. **Manual fallback** — prints instructions, returns `prompt_written`.

The ChatGPT planner similarly uses OpenAI API if `OPENAI_API_KEY` is set, otherwise writes to outbox.

---

## GitHub Integration

When `GITHUB_TOKEN` is set:
- Lists open issues and can create tasks from them.
- Comments on issues when tasks complete.
- Closes issues when merged.

Without token, all GitHub operations degrade gracefully — tasks.json only.

---

## Supabase SQL Behavior

Before any SQL execution:
1. SQL is scanned by `sql_guard.py`.
2. Blocked terms (`DROP TABLE`, `TRUNCATE`, `DELETE FROM` without WHERE, etc.) halt execution.
3. Warnings are logged for safe operations (`DROP POLICY IF EXISTS`, `ALTER TABLE`, etc.).
4. If scan passes and `AUTO_APPLY_SQL=true`, SQL is applied via Supabase client RPC.
5. If Supabase is not configured, SQL is written to a log with manual execution instructions.

---

## Resource & Credential Gate

Some tasks can't be finished without something only a human can provide — a new
API key, a service token, or access to an external resource. The
`request_resources_if_needed` node (enabled by default; disable with
`RESOURCE_GATE=false`) catches this so the runner pauses for a human instead of
committing/deploying incomplete work or looping past the gap.

How it works:

1. The worker prompt asks every worker to report **Credentials Needed** and
   **Resources Needed** — *names only, never values* — for anything it lacked
   that blocked the task (or `none`).
2. `parse_worker_summary` extracts those into `credentials_needed` /
   `resources_needed`. Placeholders (`none`, `N/A`, …) are filtered out.
3. If anything real is requested, the node writes a human-readable request to
   `outbox/<task_id>_resource_request.txt`, logs `resource_request_pending`, and
   waits for a fulfillment file at `inbox/<task_id>_resources_provided.txt`.
4. **Unfulfilled** → the task is marked `blocked`, `stop_reason` is set to
   `awaiting_resources`, a `resource_request_waiting` event is logged, and the
   loop halts cleanly at `decide_continue_or_stop` (it does **not** commit,
   deploy, or queue another task on top of the gap). Provision what's needed
   (e.g. add the credential to `.env`), create the fulfillment file, flip the
   task back to `queued`, and re-run.
5. **Fulfilled** (fulfillment file present) → the node logs
   `resource_request_fulfilled` and the loop proceeds. The fulfillment file is
   only an "unblock" signal: its contents are **never read or logged**, so
   secrets stay out of the flight recorder. The worker reports credential
   *names* only, so nothing secret is ever written to `outbox/` either.

The gate runs **regardless of worker success**, so a worker that failed *because*
it lacked a credential surfaces an actionable request rather than a bare failure.

The decision helpers in `tools/resource_gate.py` (`collect_requests`,
`evaluate_gate`, `format_request_file`) are pure/side-effect free and unit-tested
in `tests/test_resource_gate.py`, which also covers the graph node.

---

## Failure & Retry Guard

When a worker fails, `update_logs_and_state` no longer just records a bare
failure and moves on (which loses transient-failure work and lets a broken run
burn its whole loop/runtime budget producing more failures). With
`FAILURE_GUARD=true` (default) it applies two protections:

1. **Per-task retry** — the failed task is requeued (status → `queued`, its
   `retry_count` bumped) up to `MAX_TASK_RETRIES` times (default 1) before being
   marked permanently `failed`. The requeued task keeps its place in the queue,
   so `load_next_task` picks it up again on the next loop. Each retry logs a
   `task_retry_scheduled` event; the final give-up logs the usual `error` event
   with `retries_exhausted: true`. While a retry is pending the runner does
   **not** ask the planner for a fresh task — it lets the retry run first.
2. **Consecutive-failure circuit breaker** — the runner tracks how many tasks
   have failed back-to-back on `state.consecutive_failures`. Once that reaches
   `MAX_CONSECUTIVE_FAILURES` (default 3) the guard sets `stop_reason`
   (`consecutive_failures`), logs `loop_blocked_on_failures`, and the loop halts
   cleanly at `decide_continue_or_stop` instead of piling new tasks onto a run
   that's clearly going sideways. Any **successful** task resets the counter to 0.

Retry and the breaker are independent: a task with retries remaining is still
requeued for the next run even when the same failure trips the breaker and stops
this run. Set `MAX_TASK_RETRIES=0` to disable retries (fail immediately) or
`MAX_CONSECUTIVE_FAILURES=0` to disable the breaker. `FAILURE_GUARD=false`
restores the old behavior: mark failed and continue.

The decision logic in `tools/failure_guard.py` (`task_retry_count`,
`evaluate_failure`) is pure/side-effect free and unit-tested in
`tests/test_failure_guard.py`, which also covers the graph node.

---

## Vercel Behavior

The `deploy_if_needed` graph node runs after the worker's changes are committed
and any SQL is applied. It deploys **only** when the worker succeeded, checks
passed, and a commit landed — otherwise it logs `deploy_skipped` and moves on.

When `VERCEL_TOKEN` is set and a deploy runs:
- Deployment status is fetched after the merge.
- `AUTO_DEPLOY=true` triggers a deploy (scoped to `VERCEL_PROJECT_ID` when set).
- `AUTO_DEPLOY_POLL=true` (default) then **polls** the triggered deployment every
  `VERCEL_POLL_INTERVAL` seconds until it reaches a terminal state
  (`READY` / `ERROR` / `CANCELED`) or `VERCEL_POLL_TIMEOUT` seconds elapse. The
  poll verdict is returned on `trigger_deploy(...)["poll"]`, and `success` reflects
  whether the deployment actually became ready — not just whether the trigger fired.

The node records the verdict on `state.deploy_result` / `state.deploy_ready`,
emits a `deploy_result` event, and (when a GitHub issue is linked) appends the
deploy verdict to the issue comment.

When `BLOCK_ON_DEPLOY_FAILURE=true` (default), a polled deploy that **failed**
(terminal `ERROR` / `CANCELED`) or **timed out** sets `stop_reason`
(`deploy_failed` / `deploy_timed_out`), emits a `loop_blocked_on_deploy` event,
and halts the loop at `decide_continue_or_stop` — so the runner stops piling new
tasks on top of a broken deployment instead of looping past it. A degraded or
unavailable deploy (no token, API unreachable, or polling disabled) is **not**
treated as a failure and the loop continues.

`poll_deployment_until_terminal(...)` is read-only and takes injectable
`fetch`/`sleep`/`now` callables so the loop is unit-testable without the network
(see `tests/test_vercel_polling.py`; the node itself is covered by
`tests/test_deploy_node.py`).

Without token, Vercel steps are skipped with a logged note.

---

## Slack Notifications

The runner can push **notable** lifecycle events to a Slack channel via an
[Incoming Webhook](https://api.slack.com/messaging/webhooks). Notifications hang
off the flight recorder: every call to `log_event(...)` is offered to
`tools/slack_tools.py`, which posts only the events listed in
`SLACK_NOTIFY_EVENTS`.

- Set `SLACK_WEBHOOK_URL` to enable. Without it, notifications are a no-op and
  the runner is otherwise unaffected.
- `SLACK_NOTIFY=false` disables notifications without removing the webhook.
- `SLACK_NOTIFY_EVENTS` overrides which events ping Slack (comma-separated). The
  default curated set is: `task_completed`, `error`, `loop_stopped`,
  `loop_blocked_on_deploy`, `deploy_poll_failed`, `deploy_poll_timeout`,
  `sql_scan_blocked`, `sql_approval_pending`, `resource_request_pending`,
  `check_failed`.
- Reaching Slack failing (network error, non-2xx) **never** interrupts the
  runner — the failure is swallowed and recorded as a `slack_degraded` event, so
  the flight recorder keeps the full trail. `slack_degraded` is intentionally not
  in the notify set, so a Slack outage can't loop back into more Slack posts.

`format_event(...)` builds the message text and is pure/side-effect free, so the
formatting and filtering are unit-tested without the network (see
`tests/test_slack_tools.py`).

---

## SQL Scanner

```bash
python main.py scan-sql ../../supabase/my-migration.sql
```

Blocked: `DROP TABLE` (without IF EXISTS), `DROP SCHEMA`, `DROP DATABASE`, `TRUNCATE`, `DELETE FROM` (without WHERE), `UPDATE` (without WHERE).

Allowed with warnings: `DROP TABLE IF EXISTS`, `DROP POLICY IF EXISTS`, `DROP TRIGGER IF EXISTS`, `ALTER TABLE`, `CREATE TABLE`, `CREATE INDEX`, `CREATE POLICY`, `ENABLE ROW LEVEL SECURITY`.

---

## LangGraph Nodes

1. `load_next_task` — fetch next queued task from `.runtime/tasks.local.json`; rewrites protected branch names to `feature/<task-id>` and persists the rewritten branch back to the task queue before dispatch
2. `ask_chatgpt_for_task_if_needed` — ask ChatGPT for next task if queue empty
3. `choose_worker` — route to Claude or Codex based on task type
4. `generate_worker_prompt` — build structured prompt for worker
5. `dispatch_worker` — send prompt to worker, capture result
6. `capture_worker_result` — store output in state
7. `parse_worker_summary` — extract structured summary from output
8. `request_resources_if_needed` — resource/credential request gate; pauses the loop when the worker reports a missing credential/resource (see **Resource & Credential Gate**)
9. `run_checks_if_needed` — run `./scripts/check.sh`
10. `commit_push_merge_if_needed` — git commit/push/merge flow; late guard blocks any remaining protected-branch attempts
11. `apply_sql_if_needed` — scan and apply SQL migrations
12. `deploy_if_needed` — trigger a Vercel deploy and poll it to a terminal state (only when a commit landed; see **Vercel Behavior**)
13. `update_github_if_needed` — comment/close GitHub issues
14. `update_logs_and_state` — mark task complete/failed, log
15. `ask_chatgpt_next_task` — send summary back to ChatGPT
16. `decide_continue_or_stop` — check loop limits, decide to continue or stop

---

## Smoke Test

After initial setup, run through this checklist to verify the runner is working end-to-end:

```bash
cd runner/langgraph
source .venv/bin/activate

# 1. Validate config and create required files/folders
python main.py setup

# 2. Confirm .runtime/state.local.json is readable
python main.py status

# 3. Add a test task to tasks.json and confirm it appears
python main.py next-task

# 4. Run a single cycle (uses outbox mode if claude/codex are not on PATH)
python main.py run-once

# 5. Check logs to confirm an event was recorded
python main.py logs --tail 10
```

**Expected outcomes:**

| Step | Pass condition |
|------|---------------|
| `setup` | Prints "Setup complete", no errors |
| `status` | Prints valid JSON with a `status` field |
| `next-task` | Prints queued task or "No tasks queued" |
| `run-once` | Completes without Python traceback; logs a `task_started` event |
| `logs` | Shows at least one JSONL event line |

**Outbox / manual mode note:** If `claude` and `codex` are not on PATH, `run-once` will write a prompt to `outbox/<task_id>_prompt.txt` and wait. Place a response in `inbox/<task_id>_response.txt` to let the cycle finish. This is expected behavior — not a failure.

---

## Known Limitations

- Claude CLI (`claude`) must be on PATH for automatic Claude execution. Otherwise outbox/manual mode.
- Codex CLI (`codex`) must be on PATH for automatic Codex execution. Otherwise outbox/manual mode.
- Supabase arbitrary SQL execution requires a custom `exec_sql` RPC function in your Supabase project.
- Vercel trigger API may require `projectId` — set in `.env` if needed.
- `merge-feature.sh` is called for auto-merge; ensure it's executable and tested.
