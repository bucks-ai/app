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

## Task Acceptance Criteria Gate

> **Every task must carry concrete acceptance criteria before a worker is dispatched.**

The gate runs immediately after a worker is chosen (`choose_worker` → `check_acceptance_criteria` → `resolve_model`). It validates that the task dict provides unambiguous answers to five questions:

| Criterion | Field / description keyword |
|-----------|----------------------------|
| **Allowed scope** | `acceptance_criteria.allowed_scope` or "expected files / allowed scope" in description |
| **Forbidden scope** | `acceptance_criteria.forbidden_scope` or "must not modify / forbidden scope" in description |
| **Required checks** | `acceptance_criteria.required_checks` or "required checks / must pass" in description |
| **Success evidence** | `acceptance_criteria.success_evidence` or "done condition / success criteria" in description |
| **Rollback behavior** | `acceptance_criteria.rollback_behavior` or "rollback / on failure" in description |

An optional boolean field `acceptance_criteria.human_approval_required` is recognised but not required.

**Primary method (recommended):** include a structured `acceptance_criteria` dict in the task:

```json
{
  "id": "my-task",
  "title": "Add OAuth login",
  "type": "backend",
  "branch": "feature/my-task",
  "acceptance_criteria": {
    "allowed_scope": ["app/auth/", "tests/auth/"],
    "forbidden_scope": "Do not modify app UI, routes, SQL migrations, or .env files.",
    "required_checks": "check.sh must pass; auth unit tests must pass.",
    "success_evidence": "Logs task_acceptance_criteria_passed; new OAuth route returns 200.",
    "rollback_behavior": "Mark task failed; no automatic revert.",
    "human_approval_required": false
  }
}
```

**Fallback method:** keyword-scan the `description` field. A description that mentions phrases such as "allowed scope", "forbidden scope", "required checks", "done condition", and "rollback" will satisfy the gate without a structured dict.

**Logged events:**
- `task_acceptance_criteria_passed` — task has all required criteria.
- `task_acceptance_criteria_warned` — criteria missing in non-strict mode (task still runs).
- `task_acceptance_criteria_rejected` — criteria missing in strict mode (task marked failed, loop stops).

**Config:**
- `ACCEPTANCE_CRITERIA_GATE_ENABLED=true` (default) — enable validation.
- `ACCEPTANCE_CRITERIA_STRICT_MODE=false` (default) — set to `true` to block tasks missing criteria.

---

## Auto-Repair Loop v2

> **Automatic self-repair: when check.sh fails after a successful worker run, the same worker is re-dispatched with the failure output so it can fix the issues in place.**

The loop runs after `run_checks_if_needed` and before `commit_push_merge_if_needed`.  When check.sh fails but the worker itself succeeded, the runner re-dispatches the same worker (Claude or Codex) with the check failure output as context.  If the repair attempt causes checks to pass, `worker_result` is updated and the pipeline continues to commit/deploy normally.  If all attempts are exhausted (or the worker fails during repair), `check_passed` remains False and the normal failure-guard path handles the task.

**Skip conditions** — the loop does not fire when:
- `AUTO_REPAIR_LOOP_ENABLED=false`.
- The worker itself failed (failure guard handles those; the check wasn't even run).
- check.sh passed on the first attempt.
- All repair attempts have been used (`auto_repair_attempt >= MAX_AUTO_REPAIR_ATTEMPTS`).

**Logged events:**
- `auto_repair_attempted` — a repair dispatch has started (includes attempt number).
- `auto_repair_succeeded` — the repaired code passed check.sh; pipeline proceeds.
- `auto_repair_check_failed` — the repair ran but check.sh still failed; may retry.
- `auto_repair_worker_failed` — the worker itself failed during repair; loop stops.
- `auto_repair_failed` — all attempts exhausted, check still failing.

**Config:**
- `AUTO_REPAIR_LOOP_ENABLED=true` (default) — enable the loop.
- `MAX_AUTO_REPAIR_ATTEMPTS=2` (default) — maximum repair attempts per task.

---

## Codex-to-Claude Repair Escalation

> **Automatic fallback: when Codex fails, Claude tries to repair the task before the failure guard runs.**

When a Codex worker fails with a non-usage-limit error, the runner re-dispatches the same task to Claude Code as a repair attempt. If Claude succeeds, the successful output replaces the failed Codex result and the pipeline continues normally (checks, commit, deploy). If Claude also fails, state is unchanged and the normal failure-guard path handles it.

**Skip conditions** — escalation does not fire when:
- The worker was not Codex.
- Codex succeeded.
- The failure looks like an OpenAI quota / rate-limit error (`429`, `quota`, `monthly limit`, etc.) — those are tracked by `codex_usage_limit_guard` and should still accumulate so the loop can halt when Codex is persistently out of quota.
- `CODEX_TO_CLAUDE_ESCALATION_ENABLED=false`.

**Logged events:**
- `codex_escalation_attempted` — Codex failed and Claude is being tried.
- `codex_escalation_succeeded` — Claude repaired the task; pipeline proceeds with Claude's output.
- `codex_escalation_failed` — Claude also failed; original Codex failure is preserved.

**Config:**
- `CODEX_TO_CLAUDE_ESCALATION_ENABLED=true` (default) — enable the escalation.

---

## High-Risk Claude Review Gate

> **An AI-powered pre-commit review for tasks that touch sensitive code paths.**

The gate runs after `check_independent_code_review` passes and before resources are checked. It detects "high-risk" tasks and asks Claude (via the Anthropic API) to review the diff before any commit.

**High-risk detection** — a task is considered high-risk when it:
- Carries an explicit `"high_risk": true` or `"risk_level": "high"` field, **or**
- Has a title, type, or description mentioning keywords such as: `auth`, `payment`, `migration`, `sql`, `security`, `credential`, `secret`, `token`, `infrastructure`, `admin`, `delete`, `drop`, `truncate`, `encryption`, `password`, …

**Review** — Claude is asked to return exactly one of `APPROVED`, `NEEDS_REVIEW`, or `REJECTED` with a one-sentence reason.

| Verdict | Non-strict (default) | Strict mode |
|---------|----------------------|-------------|
| `APPROVED` | proceeds | proceeds |
| `NEEDS_REVIEW` | logs warning, proceeds | marks task failed, stops loop |
| `REJECTED` | logs warning, proceeds | marks task failed, stops loop |

The gate is silently skipped when:
- `HIGH_RISK_CLAUDE_REVIEW_ENABLED=false`
- The task is not high-risk
- `ANTHROPIC_API_KEY` is not configured
- The Anthropic API call fails (treated as non-blocking warning)

**Config:**
- `HIGH_RISK_CLAUDE_REVIEW_ENABLED=true` (default) — enable the gate.
- `HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE=false` (default) — set to `true` to block commits on non-APPROVED verdicts.
- `HIGH_RISK_CLAUDE_REVIEW_MODEL=claude-haiku-4-5-20251001` (default) — Anthropic model for the review call.

**Logged events:**
- `high_risk_review_approved` — Claude approved the diff.
- `high_risk_review_warned` — non-APPROVED verdict in non-strict mode (loop continues).
- `high_risk_review_rejected` — non-APPROVED verdict in strict mode (task marked failed, loop stops).
- `high_risk_review_skipped` — gate skipped (not high-risk or no API key).
- `high_risk_review_error` — Anthropic API call failed (non-blocking).

---

## Risk-Based Merge Approval Policy

> **A configurable gate that classifies merge risk and pauses the loop for human approval when risk is too high.**

The gate runs after `auto_repair_if_needed` and before `commit_push_merge_if_needed`. It classifies the risk level of the proposed merge (low / medium / high) based on several factors and then applies a configurable approval policy.

**Risk classification** — score is accumulated from:

| Factor | Score |
|--------|-------|
| Explicit `high_risk: true` or `risk_level: "high"` on the task | +3 |
| Explicit `risk_level: "medium"` | +2 |
| High-risk keywords in title/type/description (auth, payment, migration, sql, security, …) | +1 per keyword (cap: 3) |
| More than 10 files changed | +1 |
| Sensitive file patterns matched (`.sql`, `migration`, `.env`, `auth`, `admin`, `secret`, …) | +1 per pattern (cap: 2) |
| Destructive SQL in the diff (`DROP TABLE`, `TRUNCATE`, `DELETE FROM`, …) | +2 |

Risk level: score 0 → **low**, score 1–2 → **medium**, score ≥ 3 → **high**.

**Approval policies** (`MERGE_APPROVAL_POLICY`):

| Policy | Behaviour |
|--------|-----------|
| `auto` | Never pause; risk is assessed and logged only |
| `require_approval_on_high` | Pause for human approval when risk is **high** (default) |
| `require_approval_on_medium_and_high` | Pause for **medium** and **high** risk |
| `always_require` | Always require human approval before merging |

When a pause is required the gate writes a human-readable summary to `outbox/<task_id>_merge_approval_request.txt` and waits for a fulfillment file at `inbox/<task_id>_merge_approved.txt`. The loop sets `stop_reason = awaiting_merge_approval` and halts cleanly. Create the fulfillment file and re-run to proceed. Its contents are never read — existence is the unblock signal.

The gate is silently skipped when:
- `RISK_BASED_MERGE_APPROVAL_ENABLED=false`
- The worker failed or checks did not pass
- The policy does not require approval at the assessed risk level

**Config:**
- `RISK_BASED_MERGE_APPROVAL_ENABLED=true` (default) — enable the gate.
- `MERGE_APPROVAL_POLICY=require_approval_on_high` (default) — policy controlling when human approval is required.

**Logged events:**
- `merge_approval_skipped` — policy does not require approval for this risk level.
- `merge_approval_granted` — approval file found; merge proceeds.
- `merge_approval_pending` — approval required but not yet provided.
- `merge_approval_required` — gate blocked the loop (stop_reason set; outbox written).

---

## Independent Code Review Gate

> **An autonomous second look at every diff before it is committed.**

The gate runs after `check.sh` passes and re-examines the actual `git diff` alongside the worker's reported files — independent of the worker's own self-report — to catch four categories of violation:

| Check | What it catches |
|-------|----------------|
| **env-file guard** | Any `.env*` file modified (hard fail) |
| **forbidden scope** | Files whose paths appear in `acceptance_criteria.forbidden_scope` (hard fail when defined) |
| **secret patterns** | Added diff lines matching API key / password / token patterns (hard fail) |
| **allowed scope** | Changed files outside `acceptance_criteria.allowed_scope` (hard fail when defined) |

Files are collected from **both** the git diff and the worker's summary so a worker that under-reports what it touched is still caught.

**Config:**
- `INDEPENDENT_CODE_REVIEW_ENABLED=true` (default) — enable the gate.
- `INDEPENDENT_CODE_REVIEW_STRICT_MODE=false` (default) — set to `true` to block commits on failure; false logs a warning and proceeds.

**Logged events:**
- `task_code_review_passed` — all checks passed.
- `task_code_review_warned` — checks failed in non-strict mode (task still commits).
- `task_code_review_rejected` — checks failed in strict mode (task marked failed, loop stops).

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
| `AUTO_CLEANUP_BRANCHES` | Delete local and remote feature branches after successful auto-merge (default: true) |
| `AUTO_DEPLOY` | Auto-trigger Vercel (default: true) |
| `AUTO_DEPLOY_POLL` | Poll the triggered deployment until it finishes (default: true) |
| `BLOCK_ON_DEPLOY_FAILURE` | Stop the loop when a polled deploy fails or times out (default: true) |
| `ROLLBACK_REVERT_POLICY` | Recovery plan to write after a failed/timed-out deploy: `manual`, `rollback`, `revert`, `rollback_then_revert`, or `disabled` (default: `manual`) |
| `VERCEL_POLL_TIMEOUT` | Max seconds to poll a deployment before giving up (default: 180) |
| `VERCEL_POLL_INTERVAL` | Seconds between deployment status reads (default: 5) |
| `AUTO_APPLY_SQL` | Auto-apply scanned SQL (default: true) — **keep false until SQL parsing is verified** |
| `ACCEPTANCE_CRITERIA_GATE_ENABLED` | Validate that tasks include concrete acceptance criteria before executing the worker (default: true) |
| `ACCEPTANCE_CRITERIA_STRICT_MODE` | Block task execution when criteria are missing; false (default) logs a warning but proceeds |
| `CLAUDE_SUBAGENT_PACK_ENABLED` | Inject specialised subagent context into Claude worker prompts based on task type/title (default: true) |
| `CLAUDE_HOOKS_SAFETY_PACK_ENABLED` | Install and validate runner-safety PreToolUse hooks in .claude/settings.json before each Claude CLI dispatch (default: true) |
| `CLAUDE_HOOKS_SAFETY_PACK_AUTO_INSTALL` | Auto-write the safety hook when it is missing; false only validates and logs a warning (default: true) |
| `INDEPENDENT_CODE_REVIEW_ENABLED` | Run an independent code review gate after check.sh passes, scanning the diff for scope creep, .env modifications, and secret leaks (default: true) |
| `INDEPENDENT_CODE_REVIEW_STRICT_MODE` | Block the commit when the code review finds violations; false (default) logs a warning but proceeds |
| `HIGH_RISK_CLAUDE_REVIEW_ENABLED` | Run a Claude-powered review for high-risk tasks after the static code review passes (default: true) |
| `HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE` | Block the commit when Claude returns REJECTED or NEEDS_REVIEW; false (default) logs a warning but proceeds |
| `HIGH_RISK_CLAUDE_REVIEW_MODEL` | Anthropic model used for the high-risk review call (default: claude-haiku-4-5-20251001) |
| `CODEX_TO_CLAUDE_ESCALATION_ENABLED` | When Codex fails with a non-quota error, re-attempt the task via Claude Code before the failure guard runs (default: true) |
| `AUTO_REPAIR_LOOP_ENABLED` | When check.sh fails after a successful worker run, re-dispatch the same worker with the failure output so it can fix the issues (default: true) |
| `MAX_AUTO_REPAIR_ATTEMPTS` | Maximum number of inline repair attempts per task before giving up and letting the failure guard handle it (default: 2) |
| `RISK_BASED_MERGE_APPROVAL_ENABLED` | Classify merge risk and pause the loop for human approval when risk exceeds the policy threshold (default: true) |
| `MERGE_APPROVAL_POLICY` | Controls when human approval is required before merging: `auto`, `require_approval_on_high` (default), `require_approval_on_medium_and_high`, `always_require` |
| `E2E_ENABLED` | Run Playwright browser E2E smoke tests after each successful deployment (default: false — requires `python -m playwright install`) |
| `E2E_BASE_URL` | Base URL for E2E tests (e.g. `https://my-app.vercel.app`); falls back to the URL from `deploy_result` when unset |
| `E2E_TIMEOUT_MS` | Page navigation timeout in milliseconds for E2E tests (default: 15000) |
| `E2E_HEADLESS` | Run the Playwright browser headless (default: true) |
| `UI_FLOW_VALIDATION_ENABLED` | Run multi-step interactive UI flow validation after each successful deployment (default: false — requires `python -m playwright install` and `UI_FLOW_CONFIG_PATH`) |
| `UI_FLOW_CONFIG_PATH` | Path to a JSON file containing UI flow definitions (see **UI Flow Validation Runner** for format) |
| `UI_FLOW_TIMEOUT_MS` | Per-navigation/action timeout in milliseconds for UI flow validation (default: 20000) |
| `UI_FLOW_STRICT` | Block the loop when UI flow validation fails; false (default) logs a warning but proceeds |
| `HTTP_RETRY_ENABLED` | Retry transient HTTP failures (connection errors, timeouts, 5xx, 429) with exponential backoff (default: true) |
| `HTTP_RETRY_ATTEMPTS` | Maximum number of attempts per HTTP call including the first try (default: 3) |
| `HTTP_RETRY_INITIAL_WAIT_S` | Initial backoff wait in seconds; doubles with each retry (default: 1.0) |
| `HTTP_RETRY_MAX_WAIT_S` | Maximum backoff wait in seconds (default: 10.0) |
| `BUSINESS_OUTPUT_RUBRICS_ENABLED` | Score completed worker runs against business-quality rubrics (functional correctness, value alignment, completeness, risk awareness) (default: true) |
| `BUSINESS_OUTPUT_RUBRICS_STRICT_MODE` | Block the loop when rubric score is below the pass threshold; false (default) logs a warning but proceeds |
| `BUSINESS_OUTPUT_RUBRICS_PASS_THRESHOLD` | Minimum weighted rubric score (0.0–1.0) required to pass (default: 0.6) |
| `LAUNCH_READINESS_SCORECARD_ENABLED` | Score the runner system's readiness to operate at each loop start (config completeness, credentials, safety gates, operational health) (default: true) |
| `LAUNCH_READINESS_SCORECARD_STRICT_MODE` | Halt the loop when the launch readiness score is below the pass threshold; false (default) logs a warning but proceeds |
| `LAUNCH_READINESS_SCORECARD_PASS_THRESHOLD` | Minimum weighted launch readiness score (0.0–1.0) required to proceed (default: 0.7) |
| `RESOURCE_GATE` | Pause the loop when a worker reports it needs a missing credential/resource (default: true) |
| `FAILURE_GUARD` | Retry failed tasks and stop the loop on repeated failures (default: true) |
| `MAX_TASK_RETRIES` | Times a failed task is requeued before giving up (default: 1) |
| `MAX_CONSECUTIVE_FAILURES` | Consecutive failures that trip the circuit breaker and halt the loop (default: 3) |
| `CONTEXT_COMPRESSION_MAX_TOKENS` | Soft token ceiling for persisted runner messages before older context is compressed (default: 12000) |
| `CONTEXT_COMPRESSION_KEEP_RECENT` | Number of newest messages to preserve verbatim during compression (default: 4) |

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

## Context Compression

The runner keeps `state.messages` compact with deterministic local compression.
When the estimated token count exceeds `CONTEXT_COMPRESSION_MAX_TOKENS`, older
messages are replaced with one synthetic system notice and the newest
`CONTEXT_COMPRESSION_KEEP_RECENT` messages are preserved verbatim. The notice
includes counts and the latest `worker_summary_digest`, not raw worker output.

Compression runs before a new worker prompt is added and after the worker summary
digest is available. Each compression logs `context_compressed` with token/message
counts only.

---

## logs/runs.jsonl

Append-only JSONL flight recorder. Each line is a JSON event:

```json
{"event_type": "task_loaded", "timestamp": "...", "task_id": "...", "payload": {...}}
```

Event types: `task_started`, `task_loaded`, `branch_rewritten`, `branch_rewrite_persisted`, `prompt_generated`, `context_compressed`, `planner_started`, `planner_finished`, `worker_started`, `worker_finished`, `summary_captured`, `run_summary_digest`, `check_started`, `check_passed`, `check_failed`, `branch_created`, `commit_created`, `push_completed`, `merge_started`, `merge_completed`, `branch_cleanup_completed`, `deploy_skipped`, `deploy_started`, `deploy_completed`, `deploy_result`, `deploy_poll_started`, `deploy_poll_tick`, `deploy_poll_ready`, `deploy_poll_failed`, `deploy_poll_timeout`, `deploy_poll_unavailable`, `loop_blocked_on_deploy`, `rollback_revert_policy_required`, `sql_detected`, `sql_scan_passed`, `sql_scan_blocked`, `sql_applied`, `resource_request_pending`, `resource_request_waiting`, `resource_request_fulfilled`, `next_task_requested`, `loop_stopped`, `slack_degraded`, `error`

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
- Lists open issues from `GITHUB_REPO=owner/name` and imports them into `.runtime/tasks.local.json`.
- Upserts imported issue tasks by issue number, so repeated syncs refresh title/labels/body without duplicating tasks or resetting running/completed status.
- Comments on linked issues when tasks complete or fail.
- Closes linked issues after a successful checked task run.

Without token, all GitHub operations degrade gracefully — tasks.json only.

Run an explicit sync with:

```bash
python runner/langgraph/main.py sync-github-issues owner/name
```

If no repo argument is supplied, the runner uses `GITHUB_REPO` (or
`GITHUB_REPOSITORY`) from the environment.

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

When a real deploy failure or timeout occurs, `ROLLBACK_REVERT_POLICY` also
creates an explicit operator recovery plan at
`outbox/<task_id>_rollback_revert_plan.txt`, records it on
`state.rollback_revert_plan`, and emits `rollback_revert_policy_required`.
The default `manual` policy requires a human to choose between rolling back the
deployment and reverting source. `rollback`, `revert`, and
`rollback_then_revert` change the recommended action written into the plan.
`disabled` records no recovery plan. The runner does not silently mutate `main`
or call rollback APIs from this policy path; recovery stays operator-approved.

`poll_deployment_until_terminal(...)` is read-only and takes injectable
`fetch`/`sleep`/`now` callables so the loop is unit-testable without the network
(see `tests/test_vercel_polling.py`; the node itself is covered by
`tests/test_deploy_node.py`).

Without token, Vercel steps are skipped with a logged note.

---

## Playwright Browser E2E Harness

> **Automatic post-deploy browser verification: after each successful Vercel deployment the runner opens a real Chromium browser and visits the deployed URL to confirm the app is alive.**

The harness runs in the `run_e2e_if_needed` node, immediately after `deploy_if_needed` and before GitHub issue updates. It is **advisory** — E2E failures are logged but never block the loop, so a flaky test or a scenario that hasn't been tuned yet doesn't prevent a good deploy from completing.

**Skip conditions** — the harness does not run when:
- `E2E_ENABLED=false` (the default — opt-in)
- `state.deploy_ready` is falsy (the deployment wasn't confirmed ready)
- Neither `E2E_BASE_URL` nor a URL extracted from `deploy_result` is available
- `playwright` is not installed (`python -m playwright install` required)

**Scenarios** — by default `tools/playwright_harness.build_default_scenarios` returns a minimal smoke suite (homepage loads). Pass custom scenarios by extending or replacing the list in `run_e2e_suite(scenarios=[...])`.

Each scenario dict:
```json
{
  "name": "homepage loads",
  "path": "/",
  "checks": [
    {"type": "status",        "value": "ok"},
    {"type": "title_contains","value": "my app"},
    {"type": "text_contains", "value": "Welcome"}
  ]
}
```

**Logged events:**
- `e2e_passed` — all scenarios passed.
- `e2e_failed` — one or more scenarios failed (loop continues).
- `e2e_skipped` — harness skipped (disabled / not ready / playwright missing).

**Config:**
- `E2E_ENABLED=false` (default) — opt-in to enable the harness.
- `E2E_BASE_URL` — override the target URL; defaults to the URL from `deploy_result`.
- `E2E_TIMEOUT_MS=15000` (default) — per-page navigation timeout in milliseconds.
- `E2E_HEADLESS=true` (default) — run Chromium headless.

**Pure helpers** (`tools/playwright_harness.py`) — `build_default_scenarios`, `evaluate_results`, and `format_report` are side-effect free and fully unit-tested in `tests/test_playwright_harness.py`. Browser execution (`run_e2e_suite`, `run_scenario`) requires a real Playwright install.

---

## UI Flow Validation Runner

> **Multi-step interactive browser flow validation: after each successful deployment the runner executes configurable user flows (navigate → fill → click → assert) to confirm key journeys work end-to-end.**

The validator runs in the `run_ui_flow_validation_if_needed` node, immediately after `run_e2e_if_needed` and before GitHub issue updates. Like the E2E harness it is **advisory** — flow failures are logged but never block the loop (unless `UI_FLOW_STRICT=true`).

**Skip conditions** — the validator does not run when:
- `UI_FLOW_VALIDATION_ENABLED=false` (the default — opt-in)
- `state.deploy_ready` is falsy (the deployment wasn't confirmed ready)
- Neither `E2E_BASE_URL` nor a URL from `deploy_result` is available
- `playwright` is not installed (`python -m playwright install` required)
- No flows are defined (`UI_FLOW_CONFIG_PATH` not set or the file contains an empty list)

**Flow definitions** — create a JSON file (e.g. `ui_flows.json` at the repo root) and point `UI_FLOW_CONFIG_PATH` at it:

```json
[
  {
    "name": "login flow",
    "steps": [
      {"action": "navigate",   "value": "/login"},
      {"action": "fill",       "selector": "#email",    "value": "user@example.com"},
      {"action": "fill",       "selector": "#password", "value": "secret"},
      {"action": "click",      "selector": "button[type=submit]"},
      {"action": "assert_url", "value": "/dashboard"}
    ]
  },
  {
    "name": "homepage hero text",
    "steps": [
      {"action": "navigate",     "value": "/"},
      {"action": "assert_text",  "value": "Welcome to bucks.ai"}
    ]
  }
]
```

**Supported step actions:**

| Action | Required fields | Description |
|--------|----------------|-------------|
| `navigate` | `value` (path or URL) | Go to path (relative to base URL) or absolute URL |
| `click` | `selector` | Click element matching CSS selector |
| `fill` | `selector`, `value` | Type value into input matching CSS selector |
| `select` | `selector`, `value` | Select option in `<select>` matching CSS selector |
| `wait_for_selector` | `selector` | Wait for element to be visible |
| `assert_text` | `value` | Assert page body HTML contains text |
| `assert_url` | `value` | Assert current URL contains value |
| `assert_element` | `selector` | Assert element matching selector exists |

**Logged events:**
- `ui_flow_passed` — all flows passed.
- `ui_flow_failed` — one or more flows failed (loop continues unless strict mode).
- `ui_flow_skipped` — validator skipped (disabled / no URL / playwright missing / no flows).

**Config:**
- `UI_FLOW_VALIDATION_ENABLED=false` (default) — opt-in to enable the validator.
- `UI_FLOW_CONFIG_PATH` — path to the JSON file containing flow definitions.
- `UI_FLOW_TIMEOUT_MS=20000` (default) — per-navigation/action timeout in milliseconds.
- `UI_FLOW_STRICT=false` (default) — set to `true` to block the loop when flows fail.
- `E2E_BASE_URL` — shared with the E2E harness; overrides the URL from `deploy_result`.
- `E2E_HEADLESS=true` (default) — shared with the E2E harness; run Chromium headless.

**Pure helpers** (`tools/ui_flow_validator.py`) — `build_default_flows`, `evaluate_flow_results`, `format_flow_report`, and `load_flows_from_file` are side-effect free and fully unit-tested in `tests/test_ui_flow_validator.py`. Browser execution (`run_flow`, `run_ui_flow_validation`) requires a real Playwright install.

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
  `rollback_revert_policy_required`, `sql_scan_blocked`, `sql_approval_pending`,
  `resource_request_pending`, `check_failed`.
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

0b. `check_launch_readiness_if_needed` — scores the runner system across four dimensions (config completeness, credentials available, safety gates active, operational health) immediately after hook installation; writes a human-readable report to `outbox/launch_readiness_scorecard.txt`; in strict mode a failing score halts the loop before any task is dispatched
1. `load_next_task` — fetch next queued task from `.runtime/tasks.local.json`; rewrites protected branch names to `feature/<task-id>` and persists the rewritten branch back to the task queue before dispatch
2. `ask_chatgpt_for_task_if_needed` — ask ChatGPT for next task if queue empty
3. `choose_worker` — route to Claude or Codex based on task type
4. `generate_worker_prompt` — build structured prompt for worker
5. `dispatch_worker` — send prompt to worker, capture result
6. `capture_worker_result` — store output in state
6a. `escalate_to_claude_if_needed` — when Codex fails (non-quota), re-attempt via Claude Code (see **Codex-to-Claude Repair Escalation**)
7. `parse_worker_summary` — extract structured summary from output
8. `request_resources_if_needed` — resource/credential request gate; pauses the loop when the worker reports a missing credential/resource (see **Resource & Credential Gate**)
9. `run_checks_if_needed` — run `./scripts/check.sh`
9a. `auto_repair_if_needed` — when check.sh fails after a successful worker run, re-dispatch the worker with the failure output (up to MAX_AUTO_REPAIR_ATTEMPTS times; see **Auto-Repair Loop v2**)
9b. `check_merge_approval_if_needed` — classify merge risk and pause for human approval when the policy requires it (see **Risk-Based Merge Approval Policy**)
9c. `check_independent_code_review` — independent diff review for scope creep, .env modifications, and secret leaks (runs after check.sh passes; see **Independent Code Review Gate**)
9d. `check_high_risk_claude_review` — Claude-powered review for high-risk tasks (runs after static code review passes; see **High-Risk Claude Review Gate**)
10. `commit_push_merge_if_needed` — git commit/push/merge flow; late guard blocks any remaining protected-branch attempts, and successful auto-merges clean up the local and remote feature branch when `AUTO_CLEANUP_BRANCHES=true`
11. `apply_sql_if_needed` — scan and apply SQL migrations
12. `deploy_if_needed` — trigger a Vercel deploy and poll it to a terminal state (only when a commit landed; see **Vercel Behavior**)
12a. `run_e2e_if_needed` — run Playwright browser E2E smoke tests against the deployed URL (only when `E2E_ENABLED=true` and the deployment is ready; see **Playwright Browser E2E Harness**)
12b. `run_ui_flow_validation_if_needed` — execute multi-step interactive browser flows against the deployed URL (only when `UI_FLOW_VALIDATION_ENABLED=true` and `UI_FLOW_CONFIG_PATH` is set; see **UI Flow Validation Runner**)
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
