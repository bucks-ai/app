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
**Loop state:** `state.json`
**Task queue:** `tasks.json`

---

## Branch Safety

> **All generated tasks must operate on a feature branch — never on a protected branch.**

- Task `branch` field must always follow the pattern `feature/<task-id>` (e.g. `feature/operating-team-ui`).
- The runner creates the branch, commits worker output to it, and merges back to `main` only after `check.sh` passes.
- **Early guard (load_next_task):** If a task's `branch` field is set to a protected branch name (`main`, `master`, `dev`, `develop`, `production`, `release`), the runner rewrites it to `feature/<task-id>` before any worker prompt is generated. The rewritten branch is immediately persisted back to `tasks.json` so the queue reflects the correct branch name. Two log events are emitted: `branch_rewritten` (before persist) and `branch_rewrite_persisted` (after persist).
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
| `BUCKS_AI_REPO_PATH` | Path to repo (default: `/home/arnavt/bucks-ai`) |
| `RUNNER_MODE` | `browser_or_cli` (default) |
| `MAX_LOOP_TASKS` | Max tasks per run (default: 10) |
| `MAX_RUNTIME_MINUTES` | Max runtime (default: 480) |
| `AUTO_MERGE` | Auto-merge on check pass (default: true) |
| `AUTO_DEPLOY` | Auto-trigger Vercel (default: true) |
| `AUTO_APPLY_SQL` | Auto-apply scanned SQL (default: true) — **keep false until SQL parsing is verified** |

---

## CLI Commands

```bash
python main.py setup           # Validate config, create folders/files
python main.py status          # Print current state.json
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

## tasks.json Queue

Add tasks manually or let ChatGPT generate them:

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

Task types: `ui`, `frontend`, `polish` → Codex. Everything else → Claude.

> **Branch safety rule:** Tasks must **never** set `"branch": "main"`. Every task must use a feature branch in the form `feature/<task-id>`. The runner will create, push, and merge this branch automatically — writing to `main` directly bypasses all safety checks and will corrupt the loop state.

---

## logs/runs.jsonl

Append-only JSONL flight recorder. Each line is a JSON event:

```json
{"event_type": "task_loaded", "timestamp": "...", "task_id": "...", "payload": {...}}
```

Event types: `task_started`, `task_loaded`, `branch_rewritten`, `branch_rewrite_persisted`, `prompt_generated`, `planner_started`, `planner_finished`, `worker_started`, `worker_finished`, `summary_captured`, `check_started`, `check_passed`, `check_failed`, `branch_created`, `commit_created`, `push_completed`, `merge_started`, `merge_completed`, `deploy_started`, `deploy_completed`, `sql_detected`, `sql_scan_passed`, `sql_scan_blocked`, `sql_applied`, `next_task_requested`, `loop_stopped`, `error`

---

## state.json

Current loop state, updated after every node. Safe to inspect mid-run:

```json
{
  "status": "running",
  "current_task_id": "operating-team-ui",
  "current_worker": "codex",
  "loop_count": 3,
  ...
}
```

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

## Vercel Behavior

When `VERCEL_TOKEN` is set:
- Deployment status is fetched after each merge.
- `AUTO_DEPLOY=true` triggers a deploy.

Without token, Vercel steps are skipped with a logged note.

---

## SQL Scanner

```bash
python main.py scan-sql ../../supabase/my-migration.sql
```

Blocked: `DROP TABLE` (without IF EXISTS), `DROP SCHEMA`, `DROP DATABASE`, `TRUNCATE`, `DELETE FROM` (without WHERE), `UPDATE` (without WHERE).

Allowed with warnings: `DROP TABLE IF EXISTS`, `DROP POLICY IF EXISTS`, `DROP TRIGGER IF EXISTS`, `ALTER TABLE`, `CREATE TABLE`, `CREATE INDEX`, `CREATE POLICY`, `ENABLE ROW LEVEL SECURITY`.

---

## LangGraph Nodes

1. `load_next_task` — fetch next queued task from tasks.json; rewrites protected branch names to `feature/<task-id>` and persists the rewritten branch back to tasks.json before dispatch
2. `ask_chatgpt_for_task_if_needed` — ask ChatGPT for next task if queue empty
3. `choose_worker` — route to Claude or Codex based on task type
4. `generate_worker_prompt` — build structured prompt for worker
5. `dispatch_worker` — send prompt to worker, capture result
6. `capture_worker_result` — store output in state
7. `parse_worker_summary` — extract structured summary from output
8. `run_checks_if_needed` — run `./scripts/check.sh`
9. `commit_push_merge_if_needed` — git commit/push/merge flow; late guard blocks any remaining protected-branch attempts
10. `apply_sql_if_needed` — scan and apply SQL migrations
11. `update_github_if_needed` — comment/close GitHub issues
12. `update_logs_and_state` — mark task complete/failed, log
13. `ask_chatgpt_next_task` — send summary back to ChatGPT
14. `decide_continue_or_stop` — check loop limits, decide to continue or stop

---

## Smoke Test

After initial setup, run through this checklist to verify the runner is working end-to-end:

```bash
cd runner/langgraph
source .venv/bin/activate

# 1. Validate config and create required files/folders
python main.py setup

# 2. Confirm state.json is readable
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
