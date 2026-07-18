"""LangGraph StateGraph for the bucks.ai Autonomous Development Runner."""
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from state import RunnerState
from config import get_config
from tools.log_tools import log_event, update_state
from tools.task_tools import (
    get_next_queued_task,
    load_tasks,
    mark_task_running,
    mark_task_complete,
    mark_task_failed,
    mark_task_blocked,
    next_retry_eta,
    requeue_fulfilled_blocked_tasks,
    requeue_task,
    add_task,
    update_task_branch,
)
from tools.failure_guard import evaluate_failure
from tools.failure_retry_backoff import is_degraded_failure, compute_retry_not_before
from tools.repeated_error_guard import evaluate_error_repetition, evaluate_task_repetition
from tools.worker_timeout_guard import evaluate_worker_timeout
from tools.worker_health_probe import probe_worker_health
from tools.stale_run_watchdog import evaluate_stale_run
from tools.codex_usage_limit_guard import evaluate_codex_usage_limit
from tools.claude_subscription_cooldown import evaluate_subscription_cooldown
from tools.cost_budget_guard import evaluate_cost_budget
from tools.summary_tools import build_run_summary_digest, parse_worker_summary
from tools.context_compression import compress_messages
from tools.resource_gate import collect_requests, evaluate_gate, format_request_file
from tools.rollback_revert_policy import (
    evaluate_rollback_revert_policy,
    format_recovery_plan,
)
from tools.git_tools import (
    create_branch,
    run_check,
    commit_all,
    push_branch,
    merge_feature_branch,
    cleanup_feature_branch,
    fetch_pull_main,
    push_deploy_if_available,
    current_branch,
    current_commit_sha,
)
from tools.sql_guard import scan_sql_text
from tools.sql_environment_gate import evaluate_sql_approval_policy, infer_environment
from tools.supabase_tools import apply_sql_file
from tools.db_tools import (
    list_pending_migrations,
    classify_migration_additivity,
    apply_migration_file as apply_db_migration_file,
)
from tools.vercel_tools import trigger_deploy
from tools.github_tools import (
    sync_open_issues_to_tasks,
    create_pull_request,
    poll_pr_checks,
    merge_pull_request,
)
from tools.task_quality_guard import guard_planner_task
from tools.claude_hooks_safety_pack import write_hooks
from tools.acceptance_criteria_gate import guard_acceptance_criteria
from tools.definition_of_done import guard_definition_of_done
from tools.independent_code_review import guard_code_review, get_diff_text
from tools.high_risk_claude_review import guard_high_risk_claude_review
from tools.codex_to_claude_escalation import should_escalate, build_repair_prompt
from tools.auto_repair_loop import should_auto_repair, build_auto_repair_prompt
from tools.playwright_harness import run_e2e_suite, is_playwright_available
from tools.deploy_target import resolve_target_url
from tools.ui_flow_validator import (
    run_ui_flow_validation,
    load_flows_from_file,
)
from tools.product_eval_harness import (
    run_product_eval_suite,
    load_evals_from_file,
)
from tools.risk_based_merge_approval import (
    guard_merge_approval,
    format_approval_request,
    classify_merge_risk,
    requires_approval,
)
from tools.strategic_decision_gate import (
    evaluate_strategic_gate,
    format_review_file,
    STRATEGIC_GATE_STOP,
)
from tools.model_routing_policy import evaluate_model_routing_policy
from tools.launch_readiness_scorecard import guard_launch_readiness
from tools.live_batch_validation_report import generate_live_batch_report
from tools.mission_compiler import (
    parse_mission_file,
    validate_mission,
    compile_mission,
    format_mission_summary,
)
from tools.seeded_mission_queue import (
    fetch_next_queued_mission,
    fetch_mission_tasks,
    seed_tasks_from_mission,
    mark_mission_running,
    mark_mission_task_complete as mark_seeded_task_complete,
    mark_mission_task_failed as mark_seeded_task_failed,
    check_mission_completion,
    mark_mission_completed,
    mark_mission_failed,
)
from tools.agent_run_sync import start_agent_run, complete_agent_run, fail_agent_run
from tools.foreign_repo_workspace import (
    fetch_business_by_id,
    prepare_business_repo,
    resolve_scoped_github_token,
)
from workers.chatgpt_worker import ChatGPTWorker
from workers.claude_worker import ClaudeWorker
from workers.codex_worker import CodexWorker

cfg = get_config()

_PROTECTED_BRANCHES = frozenset({
    "main", "master", "dev", "develop", "production", "release",
})

_TASK_PROMPT_TEMPLATE = """You are working inside the bucks.ai repo at {repo_path}.

Task: {title}
Type: {type}
Branch: {branch}
{description_section}
Complete this task fully. When done, output a structured summary including:
- Files Created: (bullet list)
- Files Modified: (bullet list)
- Check Result: pass/fail
- Commit Result: (sha or skipped)
- Push Result: (done or skipped)
- SQL Required: yes/no
- SQL File Path: (if applicable)
- Credentials Needed: (bullet list of secret/API-key NAMES you needed but did not have — names only, never values; write "none" if none blocked you)
- Resources Needed: (bullet list of external access/services you needed but lacked — write "none" if none blocked you)
- Known Limitations: (bullet list)
- Next Task: (suggestions)
"""

# M4b: used instead of _TASK_PROMPT_TEMPLATE whenever the task's repo_path has
# been overridden to a business's sandboxed workspace (see
# resolve_business_repo_if_needed / tools/foreign_repo_workspace.py) — states
# the foreign target repo explicitly so the worker never assumes it is
# operating on the bucks-ai repo.
_BUSINESS_TASK_PROMPT_TEMPLATE = """You are working inside the customer repo {repo_full_name}, checked out at {repo_path}.

This is a BUSINESS'S OWN repository — it is NOT the bucks-ai repo. Do not
read, reference, or modify anything under the bucks-ai source tree from this
task; all file operations belong inside {repo_path}.

Task: {title}
Type: {type}
Branch: {branch}
{description_section}
Complete this task fully. When done, output a structured summary including:
- Files Created: (bullet list)
- Files Modified: (bullet list)
- Check Result: pass/fail
- Commit Result: (sha or skipped)
- Push Result: (done or skipped)
- SQL Required: yes/no
- SQL File Path: (if applicable)
- Credentials Needed: (bullet list of secret/API-key NAMES you needed but did not have — names only, never values; write "none" if none blocked you)
- Resources Needed: (bullet list of external access/services you needed but lacked — write "none" if none blocked you)
- Known Limitations: (bullet list)
- Next Task: (suggestions)
"""


def _completed_tasks() -> list[dict]:
    """Return a compact list of completed tasks for planner context."""
    return [
        {"id": t["id"], "title": t.get("title", "")}
        for t in load_tasks()
        if t.get("status") == "complete"
    ]


def _state_dict(state: RunnerState) -> dict:
    return state.model_dump()


def _persist(state: RunnerState, step: str) -> RunnerState:
    state.last_completed_step = step
    state.updated_at = datetime.utcnow().isoformat()
    update_state(_state_dict(state))
    return state


def _effective_repo_path(state: RunnerState) -> str:
    """M4b: a business mission's task carries a ``repo_path`` override (its
    isolated sandbox workspace, set by ``resolve_business_repo_if_needed``);
    every other task falls back to the runner's own ``cfg.repo_path``. This is
    the one place every git/check/diff call site should read the repo path
    from, so a business task can never accidentally operate on the bucks-ai
    repo just because a call site forgot to check for the override."""
    task = state.current_task or {}
    return task.get("repo_path") or cfg.repo_path


def _effective_github_repo(task: dict) -> Optional[str]:
    """M4b: business missions target their own sandboxed GitHub repo instead
    of the runner's own ``cfg.github_repo``."""
    return task.get("business_repo_full_name") or cfg.github_repo


def _effective_github_token(task: dict) -> Optional[str]:
    """M4b: re-resolve the scoped GitHub token fresh from the environment by
    name for a business mission — never carried across state/log events (see
    tools/foreign_repo_workspace.py::resolve_scoped_github_token)."""
    secret_name = task.get("business_github_token_secret_name")
    if not secret_name:
        return cfg.github_token
    result = resolve_scoped_github_token(secret_name)
    return result.get("token") if result["success"] else None


def _compress_context_if_needed(state: RunnerState, *, reason: str) -> RunnerState:
    result = compress_messages(
        state.messages,
        max_tokens=cfg.context_compression_max_tokens,
        keep_recent=cfg.context_compression_keep_recent,
        summary_digest=state.worker_summary_digest,
    )
    if not result["compressed"]:
        return state

    state.messages = result["messages"]
    state.context_compression = {
        "reason": reason,
        "tokens_before": result["tokens_before"],
        "tokens_after": result["tokens_after"],
        "messages_before": result["messages_before"],
        "messages_after": result["messages_after"],
        "dropped_messages": result["dropped_messages"],
    }
    log_event("context_compressed", {
        "task_id": state.current_task_id,
        **state.context_compression,
    }, task_id=state.current_task_id)
    return state


# ── Nodes ────────────────────────────────────────────────────────────────────

def install_hooks(state: RunnerState) -> RunnerState:
    """Install runner-safety hooks into .claude/settings.json at startup.

    Runs once before any task is dispatched, ensuring all Claude Code
    PreToolUse guards are active for every worker in this session.
    Skipped when the safety pack or auto-install is disabled, or in dry-run mode.
    """
    if cfg.runner_dry_run:
        log_event("dry_run_skip", {"node": "install_hooks"})
        return _persist(state, "install_hooks")
    if not cfg.claude_hooks_safety_pack_enabled or not cfg.claude_hooks_safety_pack_auto_install:
        return state

    result = write_hooks(cfg.repo_path)
    log_event("claude_hooks_installed", {
        "path": result["path"],
        "wrote": result["wrote"],
        "merged": result["merged"],
    })
    return _persist(state, "install_hooks")


def check_launch_readiness_if_needed(state: RunnerState) -> RunnerState:
    """Launch Readiness Scorecard.

    Scores the runner system across four dimensions (config completeness,
    credentials available, safety gates active, operational health) before any
    task is dispatched.  Runs once per loop start, immediately after hook
    installation.

    - Non-strict mode (default): logs a warning when the score is below
      threshold but the loop continues.
    - Strict mode (LAUNCH_READINESS_SCORECARD_STRICT_MODE=true): sets
      stop_reason so decide_continue_or_stop halts the loop cleanly.

    The scorecard report is written to outbox/launch_readiness_scorecard.txt
    for human inspection.
    """
    if not cfg.launch_readiness_scorecard_enabled:
        return state

    config_snapshot = cfg.report()
    state_snapshot = _state_dict(state)

    result = guard_launch_readiness(
        config_snapshot=config_snapshot,
        state_snapshot=state_snapshot,
        pass_threshold=cfg.launch_readiness_scorecard_pass_threshold,
        strict_mode=cfg.launch_readiness_scorecard_strict_mode,
        context="check_launch_readiness_if_needed",
    )

    state.launch_readiness_result = result

    scorecard_path = _RUNNER_DIR / "outbox" / "launch_readiness_scorecard.txt"
    scorecard_path.parent.mkdir(parents=True, exist_ok=True)
    scorecard_path.write_text(result["report"])

    if not result["passed"] and cfg.launch_readiness_scorecard_strict_mode:
        state.stop_reason = "launch_readiness_failed"

    return _persist(state, "check_launch_readiness_if_needed")


_MIGRATIONS_DIR_NAME = "supabase/migrations"


def check_pending_migrations_if_needed(state: RunnerState) -> RunnerState:
    """Startup migration awareness — the fix for merged migrations that
    silently never reach production because nothing called
    `db_tools.apply_pending_migrations`.

    Runs once per loop start, immediately after the launch readiness check.
    When DIRECT_DATABASE_URL (or DATABASE_URL) is configured, compares
    `supabase/migrations/` against the `_runner_migrations` ledger and always
    logs a loud `migrations_pending` event listing any un-applied filenames —
    this alert fires regardless of AUTO_APPLY_MIGRATIONS.

    When AUTO_APPLY_MIGRATIONS=true, additionally applies pending migrations
    in filename order, but only ones that are (a) classified additive-only by
    `db_tools.classify_migration_additivity` and (b) pass the existing
    `sql_guard` scan + `sql_environment_gate` policy inside
    `apply_migration_file`. The first non-additive or guard/gate-blocked file
    stops the auto-apply pass (later files are never applied out of order) —
    it was already surfaced via `migrations_pending` for manual application.
    """
    if not cfg.has_database:
        return state

    migrations_dir = Path(cfg.repo_path) / _MIGRATIONS_DIR_NAME
    pending_result = list_pending_migrations(str(migrations_dir))
    if not pending_result["success"]:
        log_event("error", {
            "node": "check_pending_migrations_if_needed",
            "error": pending_result["error"],
        })
        return _persist(state, "check_pending_migrations_if_needed")

    pending = pending_result["data"]["pending"]
    if not pending:
        return _persist(state, "check_pending_migrations_if_needed")

    log_event("migrations_pending", {
        "pending": pending,
        "count": len(pending),
        "auto_apply_migrations": cfg.auto_apply_migrations,
        "message": (
            f"{len(pending)} migration(s) not yet applied to the database: "
            + ", ".join(pending)
        ),
    })

    if not cfg.auto_apply_migrations:
        return _persist(state, "check_pending_migrations_if_needed")

    for filename in pending:
        file_path = migrations_dir / filename
        additivity = classify_migration_additivity(file_path.read_text())
        if not additivity["additive"]:
            log_event("migration_auto_apply_blocked", {
                "filename": filename,
                "reason": "non_additive",
                "details": additivity["reasons"],
            })
            break

        result = apply_db_migration_file(str(file_path))
        if not result["success"]:
            log_event("migration_auto_apply_blocked", {
                "filename": filename,
                "reason": result.get("error"),
                "details": result.get("data"),
            })
            break

        log_event("migration_applied", {
            "filename": filename,
            "sha256": result["data"]["sha256"],
        })

    return _persist(state, "check_pending_migrations_if_needed")


def load_next_task(state: RunnerState) -> RunnerState:
    # Auto-requeue any blocked task whose resource fulfillment file has
    # landed in inbox/ (written by the approvals daemon or by hand).
    for _tid in requeue_fulfilled_blocked_tasks(_RUNNER_DIR / "inbox"):
        log_event("resource_request_fulfilled_requeued", {
            "task_id": _tid,
            "message": "fulfillment file found in inbox/; task requeued",
        }, task_id=_tid)
    task = get_next_queued_task()
    if not task:
        # Every queued task may simply be inside its retry-backoff window —
        # there IS work, it's just ineligible for a few more seconds. Wait
        # out the shortest backoff (capped at 30 min) instead of falling
        # through to the planner and stopping the loop with chatgpt_no_task.
        eta = next_retry_eta()
        if eta:
            try:
                remaining = (datetime.fromisoformat(eta) - datetime.utcnow()).total_seconds()
            except (ValueError, TypeError):
                remaining = 0
            if 0 < remaining <= 1800:
                log_event("retry_backoff_waiting", {
                    "resume_at": eta,
                    "wait_seconds": round(remaining, 1),
                })
                time.sleep(remaining + 1)
                task = get_next_queued_task()
    if not task and cfg.has_github and cfg.github_repo:
        sync_open_issues_to_tasks(cfg.github_repo)
        task = get_next_queued_task()
    if task:
        branch = task.get("branch") or f"feature/{task['id']}"
        if branch.lower() in _PROTECTED_BRANCHES:
            safe_branch = f"feature/{task['id']}"
            log_event("branch_rewritten", {
                "task_id": task["id"],
                "original_branch": branch,
                "rewritten_branch": safe_branch,
                "reason": f"'{branch}' is a protected branch; rewritten to '{safe_branch}'",
            }, task_id=task["id"])
            task = dict(task)
            task["branch"] = safe_branch
            update_task_branch(task["id"], safe_branch)
            log_event("branch_rewrite_persisted", {
                "task_id": task["id"],
                "branch": safe_branch,
            }, task_id=task["id"])
        state.current_task = task
        state.current_task_id = task["id"]
        log_event("task_loaded", {"task": task}, task_id=task["id"])
    else:
        state.current_task = None
        state.stop_reason = "no_queued_tasks"
    return _persist(state, "load_next_task")


def compile_mission_if_needed(state: RunnerState) -> RunnerState:
    """Mission compiler: check inbox for a YAML mission file and expand it into tasks.

    Looks for the first ``.yml`` or ``.yaml`` file in ``inbox/``, parses it as
    a mission spec, and populates the task queue.  After compilation the source
    file is renamed to ``*.processed`` so the compiler does not re-expand the
    same mission on subsequent runner restarts.

    Runs only when ``MISSION_COMPILER=true`` (the default). Skipped silently
    when no mission file is found. Logs and skips on parse or validation errors
    rather than halting the loop so the runner can still ask ChatGPT for tasks.
    """
    if not cfg.mission_compiler_enabled:
        return state

    inbox = _RUNNER_DIR / "inbox"
    mission_files = sorted(inbox.glob("*.yml")) + sorted(inbox.glob("*.yaml"))

    if not mission_files:
        return state

    mission_path = mission_files[0]
    try:
        mission = parse_mission_file(mission_path)
    except Exception as e:
        log_event("mission_compiler_error", {
            "path": str(mission_path),
            "error": f"parse error: {e}",
        })
        return state

    errors = validate_mission(mission)
    if errors:
        log_event("mission_compiler_invalid", {
            "path": str(mission_path),
            "errors": errors,
        })
        return state

    tasks = compile_mission(mission)
    mission_name = mission.get("name", "mission")

    for task in tasks:
        add_task(task)

    # Write compilation summary to outbox (idempotent).
    stem = mission_path.stem
    summary_path = _RUNNER_DIR / "outbox" / f"mission_{stem}_compiled.txt"
    if not summary_path.exists():
        summary_path.write_text(format_mission_summary(mission, tasks))

    # Mark source file as processed so the compiler doesn't re-expand it.
    processed_path = Path(str(mission_path) + ".processed")
    if mission_path.exists():
        mission_path.rename(processed_path)

    state.mission_name = mission_name
    state.mission_compiled = True

    # Load the first compiled task into the current task slot and clear the
    # "no_queued_tasks" stop_reason that load_next_task set.
    task = get_next_queued_task()
    if task:
        branch = task.get("branch") or f"feature/{task['id']}"
        if branch.lower() in _PROTECTED_BRANCHES:
            safe_branch = f"feature/{task['id']}"
            task = dict(task)
            task["branch"] = safe_branch
            update_task_branch(task["id"], safe_branch)
        state.current_task = task
        state.current_task_id = task["id"]
        state.stop_reason = None

    log_event("mission_compiled", {
        "mission": mission_name,
        "task_count": len(tasks),
        "task_ids": [t["id"] for t in tasks],
        "summary_path": str(summary_path),
    })

    return _persist(state, "compile_mission_if_needed")


def seed_mission_queue_if_needed(state: RunnerState) -> RunnerState:
    """Seeded Mission Queue Executor: poll Supabase for queued missions and seed the local queue.

    Runs when the local task queue is empty (``state.current_task is None``) and
    ``SEEDED_MISSION_QUEUE=true`` (the default).  Fetches the oldest ``queued``
    mission from the Supabase ``missions`` table, converts its ``mission_tasks``
    rows into runner task dicts, adds them to the local queue, and marks the
    mission as ``running`` in Supabase.

    Each seeded task carries ``seeded_mission_id`` and ``seeded_task_id`` fields
    so that ``update_logs_and_state`` can sync completion status back to Supabase
    when the task finishes.

    Skips silently when:
      - ``SEEDED_MISSION_QUEUE=false``
      - Supabase is not configured
      - No queued missions exist (falls through to ChatGPT planner)
      - A task is already loaded (mission compiler or load_next_task found one)
    """
    if not cfg.seeded_mission_queue_enabled or not cfg.has_supabase:
        return state

    if state.current_task:
        return state

    mission = fetch_next_queued_mission()
    if not mission:
        if cfg.seeded_mission_queue_strict:
            state.stop_reason = "seeded_queue_exhausted"
            log_event("seeded_queue_exhausted", {
                "message": "No queued missions remain and SEEDED_MISSION_QUEUE_STRICT=true; halting loop.",
            })
        return state

    mission_id = str(mission.get("id", ""))
    mission_name = mission.get("name", "")

    tasks_rows = fetch_mission_tasks(mission_id)
    if not tasks_rows:
        log_event("seeded_mission_queue_empty", {
            "mission_id": mission_id,
            "mission_name": mission_name,
            "message": "Mission has no tasks; skipping.",
        })
        return state

    tasks = seed_tasks_from_mission(mission, tasks_rows)
    for task in tasks:
        add_task(task)

    mark_mission_running(mission_id)

    # Load the first seeded task into the current task slot and clear the
    # "no_queued_tasks" stop_reason so the loop continues.
    first_task = get_next_queued_task()
    if first_task:
        branch = first_task.get("branch") or f"feature/{first_task['id']}"
        if branch.lower() in _PROTECTED_BRANCHES:
            safe_branch = f"feature/{first_task['id']}"
            first_task = dict(first_task)
            first_task["branch"] = safe_branch
            update_task_branch(first_task["id"], safe_branch)
        state.current_task = first_task
        state.current_task_id = first_task["id"]
        state.stop_reason = None

    log_event("seeded_mission_queued", {
        "mission_id": mission_id,
        "mission_name": mission_name,
        "task_count": len(tasks),
        "task_ids": [t["id"] for t in tasks],
    })

    return _persist(state, "seed_mission_queue_if_needed")


def ask_chatgpt_for_task_if_needed(state: RunnerState) -> RunnerState:
    if state.current_task:
        return state
    # In strict seeded queue mode the planner is never consulted: all tasks come
    # from Supabase missions and the loop stops when the queue is exhausted (see
    # seed_mission_queue_if_needed, which already set stop_reason in this case).
    if cfg.seeded_mission_queue_enabled and cfg.seeded_mission_queue_strict:
        return state
    summary_text = state.worker_summary_digest or build_run_summary_digest(state.worker_summary)
    log_event("next_task_requested", {"summary_preview": summary_text[:200]})
    planner = ChatGPTWorker()
    new_task = planner.ask_for_next_task(summary_text, completed_tasks=_completed_tasks())
    if new_task:
        new_task = guard_planner_task(
            new_task,
            context="ask_chatgpt_for_task_if_needed",
            v2=cfg.planner_quality_gate_v2_enabled,
            scope_guard=cfg.planner_scope_guard_enabled,
        )
    if new_task:
        add_task(new_task)
        task = get_next_queued_task()
        state.current_task = task
        state.current_task_id = task["id"] if task else None
        log_event("task_loaded", {"task": new_task, "source": "chatgpt"})
    else:
        state.stop_reason = "chatgpt_no_task"
    return _persist(state, "ask_chatgpt_for_task_if_needed")


def choose_worker(state: RunnerState) -> RunnerState:
    task = state.current_task or {}
    preferred = (task.get("preferred_worker") or "").lower()
    task_type = (task.get("type") or "").lower()

    if preferred in ("claude", "codex"):
        state.current_worker = preferred
    elif task_type in ("ui", "frontend", "polish", "design"):
        state.current_worker = "codex"
    else:
        state.current_worker = "claude"

    log_event("worker_started", {"worker": state.current_worker, "task_id": state.current_task_id})
    return _persist(state, "choose_worker")


def resolve_business_repo_if_needed(state: RunnerState) -> RunnerState:
    """M4b: runner executes missions against a foreign (business) repo.

    Only tasks carrying ``business_id`` are affected — ordinary self-repo
    tasks pass through untouched. When resolution succeeds,
    ``state.current_task`` gets a ``repo_path`` override pointing at the
    business's isolated workspace (``.workspaces/<business_id>/``) plus
    ``business_repo_full_name`` / ``business_github_token_secret_name`` so the
    worker prompt and the PR/merge flow target the right repo — see
    ``tools/foreign_repo_workspace.py::prepare_business_repo``.

    CRITICAL SAFETY: this is the only place a business mission's repo_path is
    ever set, and it is always the isolated workspace path — never the
    bucks-ai repo (enforced by ``is_bucks_ai_repo`` / ``guard_business_repo_path``
    inside ``prepare_business_repo``). A sandbox_config that resolves to the
    bucks-ai repo, or a missing/unresolvable business, hard-fails the task
    and halts the loop for human review rather than silently falling back to
    the runner's own repo.

    A missing GitHub token secret or unconfigured sandbox is treated as a
    resource-gate request (name only — see tools/resource_gate.py), mirroring
    ``request_resources_if_needed``, so a human can provision it and unblock
    the loop the same way as any other missing credential.
    """
    task = state.current_task or {}
    business_id = task.get("business_id")
    if not business_id:
        return state

    task_id = state.current_task_id or task.get("id", "unknown")

    business = fetch_business_by_id(str(business_id))
    if business is None:
        state.stop_reason = "business_not_found"
        mark_task_failed(task_id, f"business {business_id} not found for sandboxed mission")
        log_event("error", {
            "task_id": task_id,
            "error": f"business_not_found: business {business_id} not found for sandboxed mission",
        }, task_id=task_id)
        return _persist(state, "resolve_business_repo_if_needed")

    result = prepare_business_repo(task, business)

    if result["success"]:
        task = dict(task)
        task["repo_path"] = result["repo_path"]
        task["business_repo_full_name"] = result["repo_full_name"]
        task["business_github_token_secret_name"] = result["github_token_secret_name"]
        state.current_task = task
        log_event("business_repo_workspace_ready", {
            "task_id": task_id,
            "business_id": business_id,
            "repo_full_name": result["repo_full_name"],
            "repo_path": result["repo_path"],
        }, task_id=task_id)
        return _persist(state, "resolve_business_repo_if_needed")

    reason = result["reason"]

    if reason == "forbidden_repo":
        state.stop_reason = "business_repo_forbidden"
        mark_task_failed(
            task_id,
            f"refused: sandbox repo_full_name '{result['repo_full_name']}' resolves to the bucks-ai repo",
        )
        log_event("error", {
            "task_id": task_id,
            "error": f"business_repo_forbidden: {result['repo_full_name']}",
        }, task_id=task_id)
        return _persist(state, "resolve_business_repo_if_needed")

    if reason == "missing_secret":
        secret_name = result["secret_name"]
        requests_dict = {"credentials": [secret_name], "resources": [], "all": [secret_name]}
        request_path = _RUNNER_DIR / "outbox" / f"{task_id}_resource_request.txt"
        provided_path = _RUNNER_DIR / "inbox" / f"{task_id}_resources_provided.txt"

        if not request_path.exists():
            request_path.write_text(format_request_file(
                task_id, task.get("title", ""), requests_dict, provided_path.name,
            ))
            log_event("resource_request_pending", {
                "task_id": task_id,
                "credentials_needed": [secret_name],
                "resources_needed": [],
                "review_path": str(request_path),
                "fulfill_by": str(provided_path),
                "message": f"Business mission needs a GitHub token secret. See {request_path.name}; create {provided_path.name} to unblock.",
            }, task_id=task_id)

        gate = evaluate_gate({"credentials_needed": [secret_name], "resources_needed": []}, provided=provided_path.exists())
        if gate["blocked"]:
            state.resource_request_status = "pending"
            state.stop_reason = "awaiting_resources"
            mark_task_blocked(task_id, f"awaiting GitHub token secret: {secret_name}")
            log_event("resource_request_waiting", {
                "task_id": task_id,
                "message": f"Waiting for fulfillment file: {provided_path}",
                "credentials_needed": [secret_name],
                "resources_needed": [],
            }, task_id=task_id)
        else:
            state.resource_request_status = "fulfilled"
            log_event("resource_request_fulfilled", {"task_id": task_id, "count": 1}, task_id=task_id)
            # Re-attempt now that the human has signalled fulfillment. This
            # only succeeds if the secret is actually present in this
            # process's environment (e.g. the runner was restarted after
            # adding it to .env) — otherwise it blocks again with the same
            # actionable request, exactly like any other credential gate.
            retry = prepare_business_repo(task, business)
            if retry["success"]:
                task = dict(task)
                task["repo_path"] = retry["repo_path"]
                task["business_repo_full_name"] = retry["repo_full_name"]
                task["business_github_token_secret_name"] = retry["github_token_secret_name"]
                state.current_task = task
            else:
                state.stop_reason = "awaiting_resources"
                mark_task_blocked(task_id, f"still awaiting GitHub token secret: {secret_name}")
        return _persist(state, "resolve_business_repo_if_needed")

    # no_sandbox_config / workspace_error — actionable, but not a security
    # violation. Surface as a resource request rather than a hard failure.
    resource_label = (
        "business sandbox_config (repo_full_name + github_token_secret_name)"
        if reason == "no_sandbox_config"
        else f"business repo workspace ({result.get('error') or reason})"
    )
    requests_dict = {"credentials": [], "resources": [resource_label], "all": [resource_label]}
    request_path = _RUNNER_DIR / "outbox" / f"{task_id}_resource_request.txt"
    provided_path = _RUNNER_DIR / "inbox" / f"{task_id}_resources_provided.txt"
    if not request_path.exists():
        request_path.write_text(format_request_file(
            task_id, task.get("title", ""), requests_dict, provided_path.name,
        ))
        log_event("resource_request_pending", {
            "task_id": task_id,
            "credentials_needed": [],
            "resources_needed": [resource_label],
            "review_path": str(request_path),
            "fulfill_by": str(provided_path),
        }, task_id=task_id)
    state.resource_request_status = "pending"
    state.stop_reason = "awaiting_resources"
    mark_task_blocked(task_id, f"business repo unavailable: {reason}")
    return _persist(state, "resolve_business_repo_if_needed")


def check_acceptance_criteria(state: RunnerState) -> RunnerState:
    """Task Acceptance Criteria Gate.

    Validates that the current task carries concrete acceptance criteria before
    a worker is dispatched. When ACCEPTANCE_CRITERIA_GATE_ENABLED is true:
    - Non-strict mode (default): logs a warning when criteria are missing but
      allows the task to proceed.
    - Strict mode (ACCEPTANCE_CRITERIA_STRICT_MODE=true): marks the task failed
      and sets stop_reason so the loop stops cleanly.
    """
    if not cfg.acceptance_criteria_gate_enabled:
        return state

    task = state.current_task or {}
    result = guard_acceptance_criteria(
        task,
        context="check_acceptance_criteria",
        strict_mode=cfg.acceptance_criteria_strict_mode,
    )

    if result["passed"]:
        state.acceptance_criteria_status = "passed"
    elif cfg.acceptance_criteria_strict_mode:
        state.acceptance_criteria_status = "failed"
        task_id = state.current_task_id or "unknown"
        state.stop_reason = "missing_acceptance_criteria"
        mark_task_failed(
            task_id,
            "missing acceptance criteria: " + "; ".join(result["issues"]),
        )
    else:
        state.acceptance_criteria_status = "warned"

    return _persist(state, "check_acceptance_criteria")


def resolve_model_node(state: RunnerState) -> RunnerState:
    worker = state.current_worker
    task = state.current_task or {}
    config_override = (
        cfg.claude_model if worker == "claude"
        else cfg.chatgpt_model if worker in ("chatgpt", "codex")
        else ""
    ) or None
    decision = evaluate_model_routing_policy(
        worker=worker,
        policy=cfg.model_routing_policy,
        task=task,
        config_model_override=config_override,
    )
    state.resolved_model = decision["resolved_model"]
    log_event("model_resolved", {
        "worker": worker,
        "resolved_model": state.resolved_model,
        "policy": decision["policy"],
        "source": decision["source"],
        "task_id": state.current_task_id,
    }, task_id=state.current_task_id)

    # Seeded-mission task start -> agent_runs row. Only tasks pulled from the
    # Supabase mission queue carry seeded_task_id/seeded_mission_id; ad-hoc
    # planner/mission-compiler tasks are left alone. Degrades silently when
    # Supabase is not configured (see tools/agent_run_sync.py).
    if task.get("seeded_task_id") and task.get("seeded_mission_id"):
        state.current_agent_run_id = start_agent_run(task)

    return _persist(state, "resolve_model")


def generate_worker_prompt(state: RunnerState) -> RunnerState:
    state = _compress_context_if_needed(state, reason="before_worker_prompt")
    task = state.current_task or {}
    description = (task.get("description") or "").strip()
    description_section = f"\nDescription:\n{description}\n" if description else ""
    repo_path = _effective_repo_path(state)
    business_repo_full_name = task.get("business_repo_full_name")
    if business_repo_full_name:
        prompt = _BUSINESS_TASK_PROMPT_TEMPLATE.format(
            repo_path=repo_path,
            repo_full_name=business_repo_full_name,
            title=task.get("title", ""),
            type=task.get("type", "general"),
            branch=task.get("branch", f"feature/{task.get('id', 'task')}"),
            description_section=description_section,
        )
    else:
        prompt = _TASK_PROMPT_TEMPLATE.format(
            repo_path=repo_path,
            title=task.get("title", ""),
            type=task.get("type", "general"),
            branch=task.get("branch", f"feature/{task.get('id', 'task')}"),
            description_section=description_section,
        )

    if cfg.fast_engineering_mode_enabled:
        from tools.fast_engineering_mode import build_engineering_context, format_engineering_injection
        ctx = build_engineering_context(str(_RUNNER_DIR))
        injection = format_engineering_injection(ctx)
        if injection:
            prompt = injection + prompt
        log_event("fast_engineering_mode_injected", {
            "task_id": state.current_task_id,
            "nodes_count": len(ctx["nodes"]),
            "tools_count": len(ctx["tools"]),
            "tests_count": len(ctx["tests"]),
        }, task_id=state.current_task_id)

    state.messages = state.messages + [{"role": "user", "content": prompt}]
    log_event("prompt_generated", {"task_id": state.current_task_id, "prompt_len": len(prompt)})
    return _persist(state, "generate_worker_prompt")


_DRY_RUN_WORKER_OUTPUT = """\
Synthetic dry-run task completed without dispatching a real worker.

- Files Created: none
- Files Modified: none
- Check Result: pass
- Commit Result: skipped
- Push Result: skipped
- SQL Required: no
- SQL File Path: N/A
- Credentials Needed: none
- Resources Needed: none
- Known Limitations: dry-run mode — no worker dispatched
- Next Task: none
"""


def dispatch_worker(state: RunnerState) -> RunnerState:
    task = state.current_task or {}
    if state.resolved_model:
        task = dict(task)
        task["resolved_model"] = state.resolved_model
    prompt = (state.messages[-1]["content"] if state.messages else "")
    mark_task_running(task.get("id", ""))

    if cfg.runner_dry_run:
        state.worker_elapsed_seconds = 0.0
        state.worker_result = {
            "worker": state.current_worker or "claude",
            "mode": "dry_run",
            "success": True,
            "output": _DRY_RUN_WORKER_OUTPUT,
            "error": None,
            "prompt_written": False,
            "prompt_path": None,
            "response_path": None,
            "api_cost": 0.0,
            "tokens_used": 0,
        }
        log_event("dry_run_skip", {"node": "dispatch_worker", "task_id": state.current_task_id})
        return _persist(state, "dispatch_worker")

    worker_type = state.current_worker or "claude"

    # ── Worker health probe ──────────────────────────────────────────────────
    if cfg.worker_health_probe_enabled:
        hp = probe_worker_health(
            worker_type=worker_type,
            claude_auth_mode=cfg.claude_auth_mode,
            has_anthropic=cfg.has_anthropic,
            has_openai=cfg.has_openai,
            health_probe_enabled=True,
            live_ping_enabled=cfg.worker_health_live_ping_enabled,
            live_ping_timeout_s=cfg.worker_health_live_ping_timeout_s,
        )
        if not hp["available"]:
            log_event("worker_health_probe_failed", {
                "worker": worker_type,
                "reason": hp["reason"],
                "task_id": state.current_task_id,
            }, task_id=state.current_task_id)
            if not state.stop_reason:
                state.stop_reason = hp["stop_reason"]
                log_event("loop_blocked_on_worker_health", {
                    "worker": worker_type,
                    "reason": hp["reason"],
                    "task_id": state.current_task_id,
                }, task_id=state.current_task_id)
            state.worker_elapsed_seconds = 0.0
            state.worker_result = {
                "worker": worker_type,
                "mode": "cli",
                "success": False,
                "output": None,
                "error": hp["reason"],
                "prompt_written": False,
                "prompt_path": None,
                "response_path": None,
                "api_cost": None,
                "tokens_used": None,
            }
            return _persist(state, "dispatch_worker")
        if hp.get("live_ping_latency_ms") is not None:
            log_event("worker_health_live_ping_ok", {
                "worker": worker_type,
                "latency_ms": hp["live_ping_latency_ms"],
                "task_id": state.current_task_id,
            }, task_id=state.current_task_id)

    if worker_type == "codex":
        worker = CodexWorker()
    else:
        worker = ClaudeWorker()

    _start = time.monotonic()
    try:
        result = worker.run_worker_prompt(prompt, task)
        state.worker_elapsed_seconds = round(time.monotonic() - _start, 2)
        state.worker_result = result.model_dump()
        log_event("worker_finished", {
            "worker": worker_type,
            "success": result.success,
            "elapsed_seconds": state.worker_elapsed_seconds,
            "task_id": state.current_task_id,
        })
    except Exception as exc:
        elapsed = round(time.monotonic() - _start, 2)
        state.worker_elapsed_seconds = elapsed
        err_msg = f"worker dispatch crashed: {type(exc).__name__}: {exc}"
        state.worker_result = {
            "worker": worker_type,
            "mode": "cli",
            "success": False,
            "output": None,
            "error": err_msg,
            "prompt_written": False,
            "prompt_path": None,
            "response_path": None,
            "api_cost": None,
            "tokens_used": None,
        }
        log_event("worker_dispatch_crash", {
            "worker": worker_type,
            "error": err_msg,
            "elapsed_seconds": elapsed,
            "task_id": state.current_task_id,
        }, task_id=state.current_task_id)
    return _persist(state, "dispatch_worker")


def capture_worker_result(state: RunnerState) -> RunnerState:
    result = state.worker_result or {}
    output = result.get("output") or ""
    if output:
        state.messages = state.messages + [{"role": "assistant", "content": output}]
    log_event("summary_captured", {"task_id": state.current_task_id, "output_len": len(output)})
    return _persist(state, "capture_worker_result")


def escalate_to_claude_if_needed(state: RunnerState) -> RunnerState:
    """Codex-to-Claude repair escalation.

    When a Codex task fails with a non-usage-limit error, re-attempt it via
    Claude Code. If Claude succeeds, ``state.worker_result`` and
    ``state.current_worker`` are updated so the rest of the pipeline (checks,
    commit, deploy) sees a successful run. If Claude also fails, state is
    unchanged and the normal failure-guard path handles it.

    Skipped when ``CODEX_TO_CLAUDE_ESCALATION_ENABLED=false`` or when the
    worker was not Codex / did not fail / failed with a usage-limit error.
    """
    if not cfg.codex_to_claude_escalation_enabled:
        return state

    result = state.worker_result or {}
    if not should_escalate(result, state.current_worker or ""):
        return state

    task = state.current_task or {}
    task_id = state.current_task_id or "unknown"
    original_prompt = state.messages[-1]["content"] if state.messages else ""

    repair_prompt = build_repair_prompt(original_prompt, result, task)

    log_event("codex_escalation_attempted", {
        "task_id": task_id,
        "codex_error": (result.get("error") or "")[:200],
    }, task_id=task_id)
    state.codex_escalation_status = "attempted"

    repair_task = dict(task)
    if state.resolved_model:
        repair_task["resolved_model"] = state.resolved_model

    worker = ClaudeWorker()
    _start = time.monotonic()
    repair_result = worker.run_worker_prompt(repair_prompt, repair_task)
    elapsed = round(time.monotonic() - _start, 2)

    if repair_result.success:
        state.worker_result = repair_result.model_dump()
        state.current_worker = "claude"
        state.worker_elapsed_seconds = elapsed
        state.codex_escalation_status = "succeeded"
        log_event("codex_escalation_succeeded", {
            "task_id": task_id,
            "elapsed_seconds": elapsed,
        }, task_id=task_id)
    else:
        state.codex_escalation_status = "failed"
        log_event("codex_escalation_failed", {
            "task_id": task_id,
            "elapsed_seconds": elapsed,
            "error": (repair_result.error or "")[:200],
        }, task_id=task_id)

    return _persist(state, "escalate_to_claude_if_needed")


def parse_worker_summary_node(state: RunnerState) -> RunnerState:
    result = state.worker_result or {}
    output = result.get("output") or ""
    summary = parse_worker_summary(output)
    digest = build_run_summary_digest(summary, task=state.current_task)
    summary["run_summary_digest"] = digest
    state.worker_summary = summary
    state.worker_summary_digest = digest
    log_event("run_summary_digest", {
        "task_id": state.current_task_id,
        "digest": digest,
        "raw_length": summary.get("raw_length"),
    }, task_id=state.current_task_id)
    state = _compress_context_if_needed(state, reason="after_worker_summary")
    return _persist(state, "parse_worker_summary")


def check_definition_of_done(state: RunnerState) -> RunnerState:
    """Definition of Done enforcement gate.

    Runs after the worker summary is parsed and checks whether the worker's
    output demonstrates the task is truly complete. Only evaluated when the
    worker reported success — a failed worker already goes through the failure
    guard path.

    When DEFINITION_OF_DONE_GATE_ENABLED is true (default):
    - Non-strict mode (default): logs a warning on DoD failure but lets the
      loop continue to commit/deploy.
    - Strict mode (DEFINITION_OF_DONE_STRICT_MODE=true): marks the task failed
      and sets stop_reason so the loop stops cleanly.
    """
    if not cfg.definition_of_done_gate_enabled:
        return state

    result = state.worker_result or {}
    if not result.get("success"):
        return state

    summary = state.worker_summary or {}
    task = state.current_task or {}
    raw_output = result.get("output") or ""
    repo_path = _effective_repo_path(state)
    diff_text = get_diff_text(repo_path)

    decision = guard_definition_of_done(
        summary=summary,
        task=task,
        raw_output=raw_output,
        context="check_definition_of_done",
        strict_mode=cfg.definition_of_done_strict_mode,
        repo_path=repo_path,
        diff_text=diff_text,
    )

    if decision["passed"]:
        state.definition_of_done_status = "passed"
    elif cfg.definition_of_done_strict_mode:
        state.definition_of_done_status = "failed"
        task_id = state.current_task_id or "unknown"
        state.stop_reason = "definition_of_done_not_met"
        mark_task_failed(
            task_id,
            "definition of done not met: " + "; ".join(decision["issues"]),
        )
    else:
        state.definition_of_done_status = "warned"

    return _persist(state, "check_definition_of_done")


def check_independent_code_review(state: RunnerState) -> RunnerState:
    """Independent Code Review Gate.

    After check.sh passes, re-examines the actual git diff and worker summary
    for scope creep, .env modifications, and secret leaks — independent of the
    worker's own self-report. When INDEPENDENT_CODE_REVIEW_STRICT_MODE=true, a
    failed review marks the task failed and halts the loop before any commit.
    """
    if not cfg.independent_code_review_enabled:
        return state

    result = state.worker_result or {}
    if not result.get("success") or not state.check_passed:
        return state

    task = state.current_task or {}
    summary = state.worker_summary or {}
    diff_text = get_diff_text(_effective_repo_path(state))

    decision = guard_code_review(
        diff_text=diff_text,
        summary=summary,
        task=task,
        context="check_independent_code_review",
        strict_mode=cfg.independent_code_review_strict_mode,
    )

    if decision["passed"]:
        state.code_review_status = "passed"
    elif cfg.independent_code_review_strict_mode:
        state.code_review_status = "failed"
        task_id = state.current_task_id or "unknown"
        state.stop_reason = "code_review_rejected"
        mark_task_failed(
            task_id,
            "independent code review rejected: " + "; ".join(decision["issues"]),
        )
    else:
        state.code_review_status = "warned"

    return _persist(state, "check_independent_code_review")


def check_high_risk_claude_review(state: RunnerState) -> RunnerState:
    """High-Risk Claude Review Gate.

    After the static Independent Code Review Gate passes, runs an AI-powered
    review for tasks that carry explicit ``high_risk: true`` / ``risk_level:
    "high"`` fields or whose title/type/description contains keywords associated
    with auth, payments, DB migrations, secrets, or infrastructure changes.

    The gate calls the Anthropic API to get a verdict (APPROVED / NEEDS_REVIEW /
    REJECTED). When ``HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE=true`` (default: false),
    a non-APPROVED verdict marks the task failed and halts the loop before any
    commit. Otherwise the verdict is logged as a warning and the loop continues.

    The gate is silently skipped when:
    - ``HIGH_RISK_CLAUDE_REVIEW_ENABLED=false``
    - The task is not high-risk
    - ``ANTHROPIC_API_KEY`` is not configured
    """
    if not cfg.high_risk_claude_review_enabled:
        return state

    result = state.worker_result or {}
    if not result.get("success") or not state.check_passed:
        return state

    task = state.current_task or {}
    summary = state.worker_summary or {}
    diff_text = get_diff_text(_effective_repo_path(state))

    decision = guard_high_risk_claude_review(
        diff_text=diff_text,
        summary=summary,
        task=task,
        context="check_high_risk_claude_review",
        strict_mode=cfg.high_risk_claude_review_strict_mode,
        model=cfg.high_risk_claude_review_model,
        claude_auth_mode=cfg.claude_auth_mode,
    )

    if decision.get("skipped"):
        state.high_risk_review_status = "skipped"
    elif decision["passed"]:
        state.high_risk_review_status = "passed"
    elif cfg.high_risk_claude_review_strict_mode:
        state.high_risk_review_status = "failed"
        task_id = state.current_task_id or "unknown"
        state.stop_reason = "high_risk_review_rejected"
        mark_task_failed(
            task_id,
            "high-risk review rejected: " + "; ".join(decision["issues"]),
        )
    else:
        state.high_risk_review_status = "warned"

    return _persist(state, "check_high_risk_claude_review")


def request_resources_if_needed(state: RunnerState) -> RunnerState:
    """Resource & credential request gate.

    When the worker reports it needs a credential (API key / token / secret) or
    an external resource it doesn't have, pause the loop and surface a
    human-actionable request — instead of committing/deploying incomplete work or
    looping past the gap. Mirrors the SQL approval gate: the request is written to
    ``outbox/`` and the loop only proceeds once a fulfillment file lands in
    ``inbox/``. Runs regardless of worker success, so a worker that failed *for
    lack of a credential* surfaces a request rather than a bare failure.

    Only credential/resource *names* are ever written or logged — never values
    (see tools/resource_gate.py). When blocked, the task is marked ``blocked`` and
    ``stop_reason`` halts the loop at ``decide_continue_or_stop``.
    """
    if not cfg.resource_gate_enabled:
        return state

    summary = state.worker_summary or {}
    requests = collect_requests(summary)
    if not requests["all"]:
        return state  # nothing requested → proceed normally

    task = state.current_task or {}
    task_id = state.current_task_id or "unknown"
    request_path = _RUNNER_DIR / "outbox" / f"{task_id}_resource_request.txt"
    provided_path = _RUNNER_DIR / "inbox" / f"{task_id}_resources_provided.txt"

    # Surface the request for a human (idempotent — only on first encounter).
    if not request_path.exists():
        request_path.write_text(format_request_file(
            task_id, task.get("title", ""), requests, provided_path.name,
        ))
        log_event("resource_request_pending", {
            "task_id": task_id,
            "credentials_needed": requests["credentials"],
            "resources_needed": requests["resources"],
            "review_path": str(request_path),
            "fulfill_by": str(provided_path),
            "message": f"Worker needs resources/credentials. See {request_path.name}; create {provided_path.name} to unblock.",
        }, task_id=task_id)

    gate = evaluate_gate(summary, provided=provided_path.exists())
    if gate["blocked"]:
        state.resource_request_status = "pending"
        state.stop_reason = "awaiting_resources"
        mark_task_blocked(task_id, "awaiting resources/credentials")
        log_event("resource_request_waiting", {
            "task_id": task_id,
            "message": f"Waiting for fulfillment file: {provided_path}",
            "credentials_needed": requests["credentials"],
            "resources_needed": requests["resources"],
        }, task_id=task_id)
    else:
        # Human signalled fulfillment (file present); never read its contents.
        state.resource_request_status = "fulfilled"
        log_event("resource_request_fulfilled", {
            "task_id": task_id,
            "count": len(requests["all"]),
        }, task_id=task_id)
    return _persist(state, "request_resources_if_needed")


def run_checks_if_needed(state: RunnerState) -> RunnerState:
    result = state.worker_result or {}
    if not result.get("success"):
        return state
    if cfg.runner_dry_run:
        state.check_passed = True
        state.check_output = "[dry-run: check skipped]"
        log_event("dry_run_skip", {"node": "run_checks_if_needed", "task_id": state.current_task_id})
        return _persist(state, "run_checks_if_needed")
    check = run_check(_effective_repo_path(state))
    state.check_passed = check["success"]
    state.check_output = check.get("output") or ""
    return _persist(state, "run_checks_if_needed")


def auto_repair_if_needed(state: RunnerState) -> RunnerState:
    """Auto-Repair Loop v2.

    When check.sh fails after a successful worker run, re-dispatch the same
    worker with the check failure output as context so it can fix the issues
    in place.  Repeats inline up to MAX_AUTO_REPAIR_ATTEMPTS times.  If a
    repair attempt causes check.sh to pass, ``check_passed`` is set True and
    ``worker_result`` is updated so the pipeline continues to commit/deploy as
    normal.  If all attempts are exhausted (or the worker itself fails during
    repair), ``check_passed`` remains False and the normal failure-guard path
    handles it.

    Skipped when:
    - ``AUTO_REPAIR_LOOP_ENABLED=false``
    - The worker itself failed (failure guard handles those)
    - check.sh passed on the first try
    - All repair attempts have been used
    """
    if not cfg.auto_repair_loop_enabled:
        return state

    result = state.worker_result or {}
    task = state.current_task or {}
    task_id = state.current_task_id or "unknown"

    while should_auto_repair(
        result,
        state.check_passed,
        state.auto_repair_attempt,
        cfg.max_auto_repair_attempts,
    ):
        attempt = state.auto_repair_attempt + 1
        state.auto_repair_attempt = attempt

        check_output = state.check_output or ""
        original_prompt = next(
            (m["content"] for m in reversed(state.messages) if m.get("role") == "user"),
            "",
        )
        repair_prompt = build_auto_repair_prompt(
            original_prompt, check_output, task, attempt, cfg.max_auto_repair_attempts
        )

        log_event("auto_repair_attempted", {
            "task_id": task_id,
            "attempt": attempt,
            "max_attempts": cfg.max_auto_repair_attempts,
            "worker": state.current_worker,
        }, task_id=task_id)

        repair_task = dict(task)
        if state.resolved_model:
            repair_task["resolved_model"] = state.resolved_model

        if state.current_worker == "codex":
            worker = CodexWorker()
        else:
            worker = ClaudeWorker()

        _start = time.monotonic()
        repair_result = worker.run_worker_prompt(repair_prompt, repair_task)
        elapsed = round(time.monotonic() - _start, 2)

        if repair_result.success:
            check = run_check(_effective_repo_path(state))
            state.check_passed = check["success"]
            state.check_output = check.get("output") or ""

            if check["success"]:
                state.worker_result = repair_result.model_dump()
                result = state.worker_result
                state.auto_repair_status = "succeeded"
                log_event("auto_repair_succeeded", {
                    "task_id": task_id,
                    "attempt": attempt,
                    "elapsed_seconds": elapsed,
                }, task_id=task_id)
                break
            else:
                log_event("auto_repair_check_failed", {
                    "task_id": task_id,
                    "attempt": attempt,
                    "elapsed_seconds": elapsed,
                }, task_id=task_id)
        else:
            state.auto_repair_status = "failed"
            log_event("auto_repair_worker_failed", {
                "task_id": task_id,
                "attempt": attempt,
                "elapsed_seconds": elapsed,
                "error": (repair_result.error or "")[:200],
            }, task_id=task_id)
            break

    if state.auto_repair_attempt > 0 and state.auto_repair_status not in ("succeeded", "failed"):
        state.auto_repair_status = "failed"
        log_event("auto_repair_failed", {
            "task_id": task_id,
            "attempts": state.auto_repair_attempt,
            "max_attempts": cfg.max_auto_repair_attempts,
        }, task_id=task_id)

    return _persist(state, "auto_repair_if_needed")


def check_merge_approval_if_needed(state: RunnerState) -> RunnerState:
    """Risk-Based Merge Approval Policy Gate.

    Classifies the risk level of the proposed merge and, when the configured
    policy requires human approval for that risk level, writes an approval
    request to outbox/ and pauses the loop until a fulfillment file lands in
    inbox/. Runs after auto-repair (checks have passed) and before any
    commit/push/merge step.

    Skipped when RISK_BASED_MERGE_APPROVAL_ENABLED=false or when the policy
    does not require approval for the assessed risk level ('auto' policy, or
    low-risk task with 'require_approval_on_high').
    """
    if not cfg.risk_based_merge_approval_enabled:
        return state

    result = state.worker_result or {}
    if not result.get("success") or not state.check_passed:
        return state

    task = state.current_task or {}
    task_id = state.current_task_id or "unknown"
    summary = state.worker_summary or {}
    diff_text = get_diff_text(_effective_repo_path(state))

    approval_path = _RUNNER_DIR / "outbox" / f"{task_id}_merge_approval_request.txt"
    provided_path = _RUNNER_DIR / "inbox" / f"{task_id}_merge_approved.txt"
    already_approved = provided_path.exists()

    decision = guard_merge_approval(
        task=task,
        diff_text=diff_text,
        summary=summary,
        policy=cfg.merge_approval_policy,
        approved=already_approved,
        context="check_merge_approval_if_needed",
    )

    if decision["skipped"]:
        state.merge_approval_status = "skipped"
        state.merge_risk_level = decision["risk_level"]
    elif decision["passed"]:
        state.merge_approval_status = "approved"
        state.merge_risk_level = decision["risk_level"]
    else:
        state.merge_approval_status = "pending"
        state.merge_risk_level = decision["risk_level"]

        if not approval_path.exists():
            approval_path.write_text(format_approval_request(
                task_id,
                task.get("title", ""),
                decision["classification"],
                provided_path.name,
            ))

        state.stop_reason = "awaiting_merge_approval"
        log_event("merge_approval_required", {
            "task_id": task_id,
            "risk_level": decision["risk_level"],
            "policy": cfg.merge_approval_policy,
            "reasons": decision["classification"]["reasons"],
            "review_path": str(approval_path),
            "approve_by": str(provided_path),
            "message": (
                f"Merge requires human approval (risk={decision['risk_level']}). "
                f"See {approval_path.name}; create {provided_path.name} to unblock."
            ),
        }, task_id=task_id)

    return _persist(state, "check_merge_approval_if_needed")


def commit_push_merge_if_needed(state: RunnerState) -> RunnerState:
    task = state.current_task or {}
    result = state.worker_result or {}
    if not result.get("success") or not state.check_passed:
        return state

    if cfg.runner_dry_run:
        log_event("dry_run_skip", {"node": "commit_push_merge_if_needed", "task_id": state.current_task_id})
        return _persist(state, "commit_push_merge_if_needed")

    branch = task.get("branch", f"feature/{task.get('id', 'task')}")

    # Late branch safety guard: block commit/push/merge to any protected branch.
    # The early guard in load_next_task should have already rewritten protected
    # branches, so reaching here with one indicates a misconfiguration.
    if branch.lower() in _PROTECTED_BRANCHES:
        log_event("error", {
            "task_id": state.current_task_id,
            "error": f"Branch safety guard: task branch '{branch}' is not allowed. Tasks must use a feature branch (e.g. feature/<task-id>).",
        })
        state.error = f"branch_guard: '{branch}' is not a valid task branch"
        return _persist(state, "commit_push_merge_if_needed")

    repo_path = _effective_repo_path(state)

    br = create_branch(repo_path, branch)
    if not br["success"]:
        return state

    state.current_branch = branch
    task_title = task.get("title", "runner task")
    commit = commit_all(repo_path, f"Complete: {task_title}")
    # A commit "landed" either when the runner created one, or when the worker had
    # already committed its own changes (clean tree -> "nothing to commit"). In both
    # cases HEAD is deployable, so record it and run push/merge — otherwise
    # deploy_if_needed wrongly skips with "no committed changes to deploy".
    if commit.get("committed"):
        state.last_commit = commit["sha"]
        push_branch(repo_path, branch)

        if cfg.auto_merge:
            if cfg.merge_via_pr:
                _merge_via_pull_request(state, task, branch)
            else:
                merge = merge_feature_branch(repo_path, branch)
                if merge.get("success"):
                    fetch_pull_main(repo_path)
                    if cfg.auto_cleanup_branches:
                        cleanup_feature_branch(repo_path, branch)

    return _persist(state, "commit_push_merge_if_needed")


def _mark_merge_step_failed(state: RunnerState, error: str) -> None:
    """Fail the task through the normal worker-result path so it feeds the same
    failure_guard / retry / circuit-breaker handling as any other worker failure
    in ``update_logs_and_state`` — the PR is left open on GitHub for inspection."""
    state.worker_result = {**(state.worker_result or {}), "success": False, "error": error}


def _merge_via_pull_request(state: RunnerState, task: dict, branch: str) -> None:
    """PR-based merge path (``MERGE_VIA_PR=true``, the default).

    Pushes have already happened by the time this runs. Opens (or reuses) a PR
    for ``branch``, polls its required checks to a terminal state, and merges
    via the API only once every check is green — branch-protection-compatible,
    unlike a local ``git merge`` + direct push to ``main``.
    """
    task_id = state.current_task_id or task.get("id", "unknown")
    repo_path = _effective_repo_path(state)
    # M4b: a business mission's PR/merge flow reuses github_tools but targets
    # the business's own sandboxed repo with its scoped token, not the
    # runner's own cfg.github_repo/cfg.github_token.
    github_repo = _effective_github_repo(task)
    github_token = _effective_github_token(task)

    if not github_repo or not github_token:
        log_event("github_degraded", {
            "reason": "no GITHUB_TOKEN/GITHUB_REPO", "action": "merge_via_pr",
        }, task_id=task_id)
        return

    title = task.get("title") or task_id
    digest = state.worker_summary_digest or build_run_summary_digest(state.worker_summary or {}, task=task, max_chars=1500)
    body = f"Automated PR for task `{task_id}`.\n\n{digest}"

    pr = create_pull_request(github_repo, branch, title, body, token=github_token)
    if not pr.get("success"):
        log_event("error", {
            "task_id": task_id,
            "error": f"pr_create_failed: {pr.get('error') or pr.get('reason')}",
        }, task_id=task_id)
        return

    if pr.get("no_diff"):
        # Branch has no commits ahead of base — the worker made no net changes.
        # Nothing to merge; leave worker_result untouched (task still succeeds)
        # and just clean up the now-redundant branch.
        log_event("pr_no_diff", {
            "task_id": task_id, "branch": branch,
            "reason": "no commits between branch and base; treated as no-op success",
        }, task_id=task_id)
        if cfg.auto_cleanup_branches:
            cleanup_feature_branch(repo_path, branch, force=True)
        return

    state.pr_number = pr.get("number")
    state.pr_url = pr.get("url")

    sha = current_commit_sha(repo_path)
    checks = poll_pr_checks(
        github_repo,
        sha,
        timeout_s=cfg.pr_checks_timeout_s,
        interval_s=cfg.pr_checks_poll_interval_s,
        pr_number=state.pr_number,
        token=github_token,
    )

    if checks.get("timed_out"):
        _mark_merge_step_failed(
            state,
            f"pr_checks_timeout: PR #{state.pr_number} required checks did not finish within {cfg.pr_checks_timeout_s}s",
        )
        return

    if checks.get("reason") == "pr_checks_no_runs":
        _mark_merge_step_failed(
            state,
            f"pr_checks_no_runs: PR #{state.pr_number} never had any check runs scheduled",
        )
        return

    if not checks.get("success"):
        _mark_merge_step_failed(
            state,
            f"pr_checks_failed: PR #{state.pr_number} required checks did not pass",
        )
        return

    merge = merge_pull_request(github_repo, state.pr_number, token=github_token)
    if not merge.get("success"):
        _mark_merge_step_failed(
            state,
            f"pr_merge_failed: PR #{state.pr_number}: {merge.get('error_body') or merge.get('error') or merge.get('reason')}",
        )
        return

    fetch_pull_main(repo_path)
    if cfg.auto_cleanup_branches:
        # force: the GitHub merge API just confirmed this branch's changes are
        # on main; a squash merge makes local `git branch -d` false-refuse.
        cleanup_feature_branch(repo_path, branch, force=True)


_RUNNER_DIR = Path(__file__).parent


def apply_sql_if_needed(state: RunnerState) -> RunnerState:
    summary = state.worker_summary or {}
    sql_required = summary.get("sql_required")
    sql_file = summary.get("sql_file_path")

    if not sql_required or not sql_file:
        return state

    # SQL environment-aware approval gate.
    # Determine effective environment (explicit config or inferred from Supabase URL).
    effective_env = cfg.sql_environment or infer_environment(cfg.supabase_url)
    # Pre-scan so the policy gate can inspect warnings/blocked terms when needed.
    try:
        pre_scan = scan_sql_text(Path(sql_file).read_text()) if cfg.sql_approval_policy == "require_on_warning" else {}
    except FileNotFoundError:
        pre_scan = {}
    gate = evaluate_sql_approval_policy(
        scan_result=pre_scan,
        sql_environment=effective_env,
        policy=cfg.sql_approval_policy,
    )
    log_event("sql_environment_gate_evaluated", {
        "policy": cfg.sql_approval_policy,
        "environment": effective_env,
        "approval_required": gate["approval_required"],
        "reason": gate["reason"],
        "task_id": state.current_task_id,
    }, task_id=state.current_task_id)

    # Approval is required when either the environment gate demands it OR the legacy
    # REQUIRE_SQL_APPROVAL flag is set and the gate defers to it (policy=auto).
    needs_approval = gate["approval_required"] or (
        cfg.sql_approval_policy == "auto" and cfg.require_sql_approval
    )

    if needs_approval:
        task_id = state.current_task_id or "unknown"
        outbox_sql = _RUNNER_DIR / "outbox" / f"{task_id}_sql_approval.sql"
        inbox_approved = _RUNNER_DIR / "inbox" / f"{task_id}_sql_approved.txt"

        # Write SQL to outbox for review (idempotent — only on first encounter).
        if not outbox_sql.exists():
            try:
                outbox_sql.write_text(Path(sql_file).read_text())
                log_event("sql_approval_pending", {
                    "task_id": task_id,
                    "sql_file": sql_file,
                    "review_path": str(outbox_sql),
                    "approve_by": str(inbox_approved),
                    "message": f"Review {outbox_sql.name}, then create {inbox_approved.name} to approve.",
                }, task_id=task_id)
            except FileNotFoundError:
                log_event("error", {"task_id": task_id, "error": f"SQL file not found: {sql_file}"})
                return _persist(state, "apply_sql_if_needed")

        # Check for human approval.
        if not inbox_approved.exists():
            state.sql_approval_status = "pending"
            log_event("sql_approval_waiting", {
                "task_id": task_id,
                "message": f"Waiting for approval file: {inbox_approved}",
            }, task_id=task_id)
            return _persist(state, "apply_sql_if_needed")

        approval_text = inbox_approved.read_text().strip().lower()
        if approval_text in ("rejected", "reject", "no"):
            state.sql_approval_status = "rejected"
            log_event("sql_approval_rejected", {"task_id": task_id}, task_id=task_id)
            return _persist(state, "apply_sql_if_needed")

        state.sql_approval_status = "approved"
        log_event("sql_approval_granted", {"task_id": task_id}, task_id=task_id)

    result = apply_sql_file(sql_file)
    state.sql_scan = result.get("scan")

    # SQL summary safety guard: only log sql_scan_blocked when the scanner blocked the SQL;
    # use a distinct event for other failure reasons (e.g. no Supabase config, auto_apply off).
    if result.get("success"):
        log_event("sql_applied", {"result": result, "task_id": state.current_task_id})
    elif result.get("reason") == "sql_scan_blocked":
        log_event("sql_scan_blocked", {"scan": result.get("scan"), "task_id": state.current_task_id})
    else:
        log_event("sql_scan_passed", {"result": result, "task_id": state.current_task_id})
    return _persist(state, "apply_sql_if_needed")


def deploy_if_needed(state: RunnerState) -> RunnerState:
    """Trigger a Vercel deploy and poll it to a terminal state.

    Runs after the worker's changes have been committed (and SQL applied) so the
    runner reports a real deploy verdict — READY vs failed/timed-out — instead of
    leaving ``trigger_deploy`` unused. Skips cleanly when nothing landed, when
    ``AUTO_DEPLOY`` is off, or when no ``VERCEL_TOKEN`` is configured.
    """
    result = state.worker_result or {}

    # Only deploy when the worker succeeded, checks passed, and a commit landed.
    if not result.get("success") or not state.check_passed or not state.last_commit:
        log_event("deploy_skipped", {
            "task_id": state.current_task_id,
            "reason": "no committed changes to deploy",
        }, task_id=state.current_task_id)
        return state

    if not cfg.auto_deploy:
        log_event("deploy_skipped", {
            "task_id": state.current_task_id,
            "reason": "AUTO_DEPLOY=false",
        }, task_id=state.current_task_id)
        return _persist(state, "deploy_if_needed")

    if not cfg.has_vercel:
        log_event("deploy_skipped", {
            "task_id": state.current_task_id,
            "reason": "no VERCEL_TOKEN",
        }, task_id=state.current_task_id)
        return _persist(state, "deploy_if_needed")

    deploy = trigger_deploy(project_id=cfg.vercel_project_id)
    state.deploy_result = deploy
    state.deploy_ready = bool(deploy.get("success"))
    poll = deploy.get("poll") or {}
    log_event("deploy_result", {
        "task_id": state.current_task_id,
        "success": deploy.get("success"),
        "ready": poll.get("ready"),
        "state": poll.get("state"),
        "timed_out": poll.get("timed_out"),
        "polls": poll.get("polls"),
        "elapsed": poll.get("elapsed"),
    }, task_id=state.current_task_id)

    # Block the loop on a deploy that reached Vercel but failed or timed out.
    # Only a polled terminal failure (ERROR / CANCELED / ...) or a poll timeout
    # halts the loop — a degraded/unavailable deploy (no token, API unreachable,
    # or polling disabled) is not a deploy failure and lets the loop continue.
    # Setting stop_reason here lets decide_continue_or_stop end the run cleanly,
    # so the runner doesn't pile new tasks on top of a broken deployment.
    if cfg.block_on_deploy_failure and not state.deploy_ready:
        timed_out = bool(poll.get("timed_out"))
        failed = bool(poll.get("terminal")) and not poll.get("ready")
        if timed_out or failed:
            reason = "deploy_timed_out" if timed_out else "deploy_failed"
            state.stop_reason = reason
            log_event("loop_blocked_on_deploy", {
                "task_id": state.current_task_id,
                "reason": reason,
                "state": poll.get("state"),
                "polls": poll.get("polls"),
                "elapsed": poll.get("elapsed"),
            }, task_id=state.current_task_id)

    decision = evaluate_rollback_revert_policy(
        deploy_result=deploy,
        policy=cfg.rollback_revert_policy,
        task=state.current_task,
        commit_sha=state.last_commit,
    )
    state.rollback_revert_status = decision.get("status")
    state.rollback_revert_plan = decision if decision.get("required") else None
    if decision.get("required"):
        task_id = state.current_task_id or "unknown"
        plan_path = _RUNNER_DIR / "outbox" / f"{task_id}_rollback_revert_plan.txt"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        if not plan_path.exists():
            plan_path.write_text(format_recovery_plan(decision))
        log_event("rollback_revert_policy_required", {
            "task_id": task_id,
            "policy": decision.get("policy"),
            "recommended_action": decision.get("recommended_action"),
            "reason": decision.get("reason"),
            "plan_path": str(plan_path),
            "warnings": decision.get("warnings", []),
        }, task_id=task_id)

    return _persist(state, "deploy_if_needed")


def run_e2e_if_needed(state: RunnerState) -> RunnerState:
    """Playwright Browser E2E Harness.

    Runs a browser-based E2E smoke suite against the deployed application URL
    after a successful Vercel deployment.  Skipped when:
    - ``E2E_ENABLED=false`` (default)
    - The deployment was not ready (``state.deploy_ready`` is falsy)
    - Neither ``E2E_BASE_URL`` nor a URL from ``deploy_result`` is available
    - playwright is not installed

    Results are stored on ``state.e2e_result`` and logged as ``e2e_passed`` or
    ``e2e_failed``.  Failure never blocks the loop — the harness is advisory so
    a flaky E2E suite doesn't prevent a good commit from landing.
    """
    if not cfg.e2e_enabled:
        return state

    if not state.deploy_ready:
        log_event("e2e_skipped", {
            "task_id": state.current_task_id,
            "reason": "deploy not ready",
        }, task_id=state.current_task_id)
        return state

    if not is_playwright_available():
        log_event("e2e_skipped", {
            "task_id": state.current_task_id,
            "reason": "playwright not installed",
        }, task_id=state.current_task_id)
        return state

    base_url, url_source = resolve_target_url(cfg.e2e_base_url, state.deploy_result)
    if not base_url:
        log_event("e2e_skipped", {
            "task_id": state.current_task_id,
            "reason": "no E2E_BASE_URL and no URL in deploy_result",
        }, task_id=state.current_task_id)
        return state

    log_event("deploy_url_validated", {
        "task_id": state.current_task_id,
        "harness": "e2e",
        "url": base_url,
        "source": url_source,
    }, task_id=state.current_task_id)

    result = run_e2e_suite(
        base_url=base_url,
        timeout_ms=cfg.e2e_timeout_ms,
        headless=cfg.e2e_headless,
    )
    state.e2e_result = result

    event_type = "e2e_passed" if result["success"] else "e2e_failed"
    log_event(event_type, {
        "task_id": state.current_task_id,
        "base_url": base_url,
        "total": len(result.get("results", [])),
        "passed_count": sum(1 for r in result.get("results", []) if r.get("passed")),
        "failed": [r["name"] for r in result.get("results", []) if not r.get("passed")],
        "error": result.get("error"),
        "screenshot_paths": [
            r["screenshot_path"] for r in result.get("results", []) if r.get("screenshot_path")
        ],
    }, task_id=state.current_task_id)

    return _persist(state, "run_e2e_if_needed")


def run_ui_flow_validation_if_needed(state: RunnerState) -> RunnerState:
    """UI Flow Validation Runner.

    Executes multi-step interactive Playwright flows (navigate, click, fill, etc.)
    against the deployed application URL after a successful Vercel deployment.
    Skipped when:
    - ``UI_FLOW_VALIDATION_ENABLED=false`` (default — opt-in)
    - The deployment was not ready (``state.deploy_ready`` is falsy)
    - Neither ``E2E_BASE_URL`` nor a URL from ``deploy_result`` is available
    - playwright is not installed
    - No flows are defined (``UI_FLOW_CONFIG_PATH`` not set or file empty)

    Flows are loaded from the JSON file at ``UI_FLOW_CONFIG_PATH``.  Results are
    stored on ``state.ui_flow_result`` and logged as ``ui_flow_passed`` or
    ``ui_flow_failed``.  Failures are advisory and never block the loop unless
    ``UI_FLOW_STRICT=true``.
    """
    if not cfg.ui_flow_validation_enabled:
        return state

    if not state.deploy_ready:
        log_event("ui_flow_skipped", {
            "task_id": state.current_task_id,
            "reason": "deploy not ready",
        }, task_id=state.current_task_id)
        return state

    if not is_playwright_available():
        log_event("ui_flow_skipped", {
            "task_id": state.current_task_id,
            "reason": "playwright not installed",
        }, task_id=state.current_task_id)
        return state

    base_url, url_source = resolve_target_url(cfg.e2e_base_url, state.deploy_result)
    if not base_url:
        log_event("ui_flow_skipped", {
            "task_id": state.current_task_id,
            "reason": "no base URL available (set E2E_BASE_URL or ensure deploy_result contains a URL)",
        }, task_id=state.current_task_id)
        return state

    flows: list = []
    if cfg.ui_flow_config_path:
        flows = load_flows_from_file(cfg.ui_flow_config_path)

    if not flows:
        log_event("ui_flow_skipped", {
            "task_id": state.current_task_id,
            "reason": "no flows defined (set UI_FLOW_CONFIG_PATH to a ui_flows.json file)",
        }, task_id=state.current_task_id)
        return state

    log_event("deploy_url_validated", {
        "task_id": state.current_task_id,
        "harness": "ui_flow",
        "url": base_url,
        "source": url_source,
    }, task_id=state.current_task_id)

    result = run_ui_flow_validation(
        base_url=base_url,
        flows=flows,
        timeout_ms=cfg.ui_flow_timeout_ms,
        headless=cfg.e2e_headless,
    )
    state.ui_flow_result = result

    event_type = "ui_flow_passed" if result["success"] else "ui_flow_failed"
    log_event(event_type, {
        "task_id": state.current_task_id,
        "base_url": base_url,
        "total": len(result.get("results", [])),
        "passed_count": sum(1 for r in result.get("results", []) if r.get("passed")),
        "failed": [r["name"] for r in result.get("results", []) if not r.get("passed")],
        "error": result.get("error"),
        "screenshot_paths": [
            r["screenshot_path"] for r in result.get("results", []) if r.get("screenshot_path")
        ],
    }, task_id=state.current_task_id)

    return _persist(state, "run_ui_flow_validation_if_needed")


def run_product_eval_if_needed(state: RunnerState) -> RunnerState:
    """Product Evaluation Harness.

    Runs HTTP-based product assertions against the deployed application URL
    after a successful Vercel deployment.  Skipped when:
    - ``PRODUCT_EVAL_ENABLED=false`` (default — opt-in)
    - The deployment was not ready (``state.deploy_ready`` is falsy)
    - Neither ``E2E_BASE_URL`` nor a URL from ``deploy_result`` is available
    - No evals are defined (``PRODUCT_EVAL_CONFIG_PATH`` not set or file empty)

    Results are stored on ``state.product_eval_result`` and logged as
    ``product_eval_passed`` or ``product_eval_failed``.  Failure never blocks
    the loop unless ``PRODUCT_EVAL_STRICT=true``.
    """
    if not cfg.product_eval_enabled:
        return state

    if not state.deploy_ready:
        log_event("product_eval_skipped", {
            "task_id": state.current_task_id,
            "reason": "deploy not ready",
        }, task_id=state.current_task_id)
        return state

    base_url = cfg.e2e_base_url
    if not base_url:
        deploy = state.deploy_result or {}
        base_url = deploy.get("url") or deploy.get("deployment_url")
    if not base_url:
        log_event("product_eval_skipped", {
            "task_id": state.current_task_id,
            "reason": "no E2E_BASE_URL and no URL in deploy_result",
        }, task_id=state.current_task_id)
        return state

    evals: list[dict] = []
    if cfg.product_eval_config_path:
        evals = load_evals_from_file(cfg.product_eval_config_path)

    if not evals:
        log_event("product_eval_skipped", {
            "task_id": state.current_task_id,
            "reason": "no evals defined (set PRODUCT_EVAL_CONFIG_PATH to a product_evals.json file)",
        }, task_id=state.current_task_id)
        return state

    result = run_product_eval_suite(
        base_url=base_url,
        evals=evals,
        timeout_ms=cfg.product_eval_timeout_ms,
    )
    state.product_eval_result = result

    event_type = "product_eval_passed" if result["success"] else "product_eval_failed"
    log_event(event_type, {
        "task_id": state.current_task_id,
        "base_url": base_url,
        "total": len(result.get("results", [])),
        "passed_count": sum(1 for r in result.get("results", []) if r.get("passed")),
        "failed": [r["name"] for r in result.get("results", []) if not r.get("passed")],
        "error": result.get("error"),
    }, task_id=state.current_task_id)

    if not result["success"] and cfg.product_eval_strict:
        state.stop_reason = "product_eval_failed"

    return _persist(state, "run_product_eval_if_needed")


def update_github_if_needed(state: RunnerState) -> RunnerState:
    if not cfg.has_github or not cfg.github_repo:
        return state
    summary = state.worker_summary or {}
    task = state.current_task or {}
    issue_number = task.get("issue_number")
    if issue_number:
        from tools.github_tools import update_issue_for_task_result
        digest = state.worker_summary_digest or build_run_summary_digest(summary, task=task, max_chars=500)
        deploy_verdict = None
        if state.deploy_result is not None:
            poll = (state.deploy_result or {}).get("poll") or {}
            deploy_verdict = "ready" if state.deploy_ready else (poll.get("state") or "not ready")
        result = state.worker_result or {}
        success = bool(result.get("success") and state.check_passed)
        update = update_issue_for_task_result(
            cfg.github_repo,
            task,
            digest,
            success=success,
            deploy_verdict=deploy_verdict,
        )
        log_event("github_issue_updated", {
            "task_id": state.current_task_id,
            "repo": cfg.github_repo,
            **update,
        }, task_id=state.current_task_id)
    return _persist(state, "update_github_if_needed")


def update_logs_and_state(state: RunnerState) -> RunnerState:
    task = state.current_task or {}
    result = state.worker_result or {}
    task_id = task.get("id", "")

    # ── Repeated-task guard ──────────────────────────────────────────────────
    if task_id:
        rep_task = evaluate_task_repetition(
            task_id, state.task_attempt_counts, cfg.max_task_attempts
        )
        counts = dict(state.task_attempt_counts)
        counts[task_id] = rep_task["attempt_count"]
        state.task_attempt_counts = counts
        if rep_task["blocked"] and not state.stop_reason:
            state.stop_reason = rep_task["stop_reason"]
            log_event("loop_blocked_on_repeated_task", {
                "task_id": task_id,
                "attempt_count": rep_task["attempt_count"],
                "max_task_attempts": cfg.max_task_attempts,
            }, task_id=task_id)

    if result.get("success"):
        digest = state.worker_summary_digest or build_run_summary_digest(state.worker_summary, task=task, max_chars=500)
        mark_task_complete(task_id, digest[:500])
        log_event("task_completed", {"task_id": task_id}, task_id=task_id)
        # A success breaks any failure streak and clears the retry signal.
        state.consecutive_failures = 0
        state.retry_pending = False
        state.last_task_completed_at = datetime.utcnow().isoformat()
        state.stale_run_warning_sent = False
    else:
        err = result.get("error") or "worker returned no output"
        state.retry_pending = False

        # ── Repeated-error guard ─────────────────────────────────────────────
        rep_err = evaluate_error_repetition(
            err, state.error_history, cfg.max_repeated_errors, cfg.repeated_error_window
        )
        state.error_history = list(state.error_history) + [{"error": err, "task_id": task_id}]
        if rep_err["blocked"] and not state.stop_reason:
            state.stop_reason = rep_err["stop_reason"]
            log_event("loop_blocked_on_repeated_error", {
                "task_id": task_id,
                "match_count": rep_err["match_count"],
                "max_repeated_errors": cfg.max_repeated_errors,
                "error": err,
            }, task_id=task_id)

        # ── Worker timeout guard ─────────────────────────────────────────────
        if cfg.worker_timeout_guard_enabled:
            tg = evaluate_worker_timeout(
                state.worker_elapsed_seconds,
                err,
                state.worker_timeout_count,
                cfg.max_worker_timeouts,
                cfg.worker_timeout_threshold,
            )
            state.worker_timeout_count = tg["timeout_count"]
            if tg["timed_out"]:
                log_event("worker_timeout_detected", {
                    "task_id": task_id,
                    "elapsed_seconds": state.worker_elapsed_seconds,
                    "timeout_count": tg["timeout_count"],
                    "max_worker_timeouts": cfg.max_worker_timeouts,
                }, task_id=task_id)
            if tg["blocked"] and not state.stop_reason:
                state.stop_reason = tg["stop_reason"]
                log_event("loop_blocked_on_worker_timeout", {
                    "task_id": task_id,
                    "timeout_count": tg["timeout_count"],
                    "max_worker_timeouts": cfg.max_worker_timeouts,
                }, task_id=task_id)

        # ── Codex usage-limit guard ──────────────────────────────────────────
        if cfg.codex_usage_limit_guard_enabled:
            cug = evaluate_codex_usage_limit(
                err,
                result.get("worker"),
                state.codex_usage_limit_count,
                cfg.max_codex_usage_limit_errors,
            )
            state.codex_usage_limit_count = cug["usage_limit_count"]
            if cug["usage_limit_detected"]:
                log_event("codex_usage_limit_detected", {
                    "task_id": task_id,
                    "usage_limit_count": cug["usage_limit_count"],
                    "max_codex_usage_limit_errors": cfg.max_codex_usage_limit_errors,
                }, task_id=task_id)
            if cug["blocked"] and not state.stop_reason:
                state.stop_reason = cug["stop_reason"]
                log_event("loop_blocked_on_codex_usage_limit", {
                    "task_id": task_id,
                    "usage_limit_count": cug["usage_limit_count"],
                    "max_codex_usage_limit_errors": cfg.max_codex_usage_limit_errors,
                }, task_id=task_id)

        # ── Claude subscription cooldown guard ───────────────────────────────
        # Detect Claude.ai subscription rate-limit responses and schedule
        # an auto-resume instead of counting this as a task failure.  When
        # detected the task is requeued with a future retry_not_before
        # timestamp and the failure guard is bypassed for this iteration.
        _cooldown_detected = False
        if cfg.claude_subscription_cooldown_enabled:
            csc = evaluate_subscription_cooldown(
                result.get("output"),
                err,
                result.get("worker"),
                cfg.claude_auth_mode,
                enabled=True,
                default_wait_s=cfg.claude_subscription_cooldown_wait_s,
                cooldown_count=state.claude_subscription_cooldown_count,
                max_cooldown_waits=cfg.claude_subscription_cooldown_max_waits,
            )
            state.claude_subscription_cooldown_count = csc["cooldown_count"]
            if csc["detected"]:
                _cooldown_detected = True
                state.claude_subscription_cooldown_until = csc["resume_at_iso"]
                log_event("claude_subscription_cooldown_detected", {
                    "task_id": task_id,
                    "wait_seconds": csc["wait_seconds"],
                    "resume_at": csc["resume_at_iso"],
                    "cooldown_count": csc["cooldown_count"],
                    "max_cooldown_waits": cfg.claude_subscription_cooldown_max_waits,
                }, task_id=task_id)
                if csc["blocked"] and not state.stop_reason:
                    state.stop_reason = csc["stop_reason"]
                    log_event("loop_blocked_on_claude_subscription_cooldown", {
                        "task_id": task_id,
                        "cooldown_count": csc["cooldown_count"],
                        "max_cooldown_waits": cfg.claude_subscription_cooldown_max_waits,
                    }, task_id=task_id)
                else:
                    # Requeue the task for when the cooldown expires (no retry
                    # count increment — this is not a task failure).
                    current_retry_count = task.get("retry_count", 0)
                    requeue_task(task_id, current_retry_count, csc["resume_at_iso"])
                    state.retry_pending = True

        if not _cooldown_detected:
            if cfg.failure_guard_enabled:
                decision = evaluate_failure(
                    task,
                    state.consecutive_failures,
                    max_task_retries=cfg.max_task_retries,
                    max_consecutive_failures=cfg.max_consecutive_failures,
                )
                state.consecutive_failures = decision["consecutive_failures"]

                if decision["action"] == "retry":
                    # Transient failure: requeue the task for another attempt.
                    # Under degraded conditions (timeout, health-probe failure,
                    # sustained consecutive failures) apply exponential backoff so
                    # the runner doesn't immediately hammer the same broken wall.
                    retry_not_before = None
                    degraded = (
                        cfg.failure_retry_backoff_enabled
                        and is_degraded_failure(
                            err,
                            state.worker_elapsed_seconds,
                            cfg.worker_timeout_threshold,
                            state.consecutive_failures,
                        )
                    )
                    if degraded:
                        retry_not_before = compute_retry_not_before(
                            decision["retry_count"],
                            cfg.failure_retry_backoff_base_s,
                            cfg.failure_retry_backoff_multiplier,
                            cfg.failure_retry_backoff_max_s,
                        )
                    requeue_task(task_id, decision["retry_count"], retry_not_before)
                    state.retry_pending = True
                    log_event("task_retry_scheduled", {
                        "task_id": task_id,
                        "error": err,
                        "attempt": decision["retry_count"],
                        "max_retries": cfg.max_task_retries,
                        "degraded": degraded,
                        "retry_not_before": retry_not_before,
                    }, task_id=task_id)
                else:
                    # Retries exhausted (or disabled): record a permanent failure.
                    mark_task_failed(task_id, err)
                    log_event("error", {
                        "task_id": task_id,
                        "error": err,
                        "retries_exhausted": cfg.max_task_retries > 0,
                    })

                # Circuit breaker: too many back-to-back failures halts the loop so the
                # runner stops piling tasks onto a run that's clearly going sideways.
                # Independent of the retry decision — the requeued task is preserved
                # for the next run while this run stops cleanly.
                if decision["circuit_open"]:
                    state.stop_reason = decision["stop_reason"]
                    log_event("loop_blocked_on_failures", {
                        "task_id": task_id,
                        "consecutive_failures": state.consecutive_failures,
                        "max_consecutive_failures": cfg.max_consecutive_failures,
                    }, task_id=task_id)
            else:
                mark_task_failed(task_id, err)
                log_event("error", {"task_id": task_id, "error": err})

    # ── Cost & budget guard ──────────────────────────────────────────────────
    if cfg.cost_budget_guard_enabled:
        task_cost = (result.get("api_cost") or 0.0) or cfg.estimated_cost_per_task_dollars
        cb = evaluate_cost_budget(
            task_cost=task_cost,
            session_cost=state.session_cost,
            max_session_cost=cfg.max_session_cost_dollars,
            max_task_cost=cfg.max_task_cost_dollars,
        )
        state.session_cost = cb["session_cost"]
        if task_cost > 0:
            log_event("cost_per_worker_run", {
                "task_id": task_id,
                "task_cost": cb["task_cost"],
                "session_cost": cb["session_cost"],
            }, task_id=task_id)
        if cb["blocked"] and not state.stop_reason:
            state.stop_reason = cb["stop_reason"]
            log_event("loop_blocked_on_cost_budget", {
                "task_id": task_id,
                "task_cost": cb["task_cost"],
                "session_cost": cb["session_cost"],
                "max_session_cost": cfg.max_session_cost_dollars,
                "max_task_cost": cfg.max_task_cost_dollars,
                "task_exceeded": cb["task_exceeded"],
                "session_exceeded": cb["session_exceeded"],
            }, task_id=task_id)

    # ── Seeded mission sync ──────────────────────────────────────────────────
    # Propagate task completion/failure back to Supabase when the task was
    # seeded from a mission row.  Only the Supabase row IDs are used here —
    # no credentials or secret values are read from the task dict.
    seeded_task_id = task.get("seeded_task_id")
    seeded_mission_id = task.get("seeded_mission_id")
    if seeded_task_id and seeded_mission_id and cfg.seeded_mission_queue_enabled and cfg.has_supabase:
        if result.get("success"):
            _sync_digest = state.worker_summary_digest or build_run_summary_digest(
                state.worker_summary, task=task, max_chars=500
            )
            mark_seeded_task_complete(seeded_task_id, _sync_digest[:500])
            if state.current_agent_run_id:
                complete_agent_run(
                    state.current_agent_run_id,
                    _sync_digest[:2000],
                    output=state.worker_summary,
                    cost_usd=result.get("api_cost"),
                    duration_seconds=state.worker_elapsed_seconds,
                )
        else:
            _sync_err = result.get("error") or "worker returned no output"
            mark_seeded_task_failed(seeded_task_id, _sync_err[:500])
            if state.current_agent_run_id:
                fail_agent_run(
                    state.current_agent_run_id,
                    _sync_err[:2000],
                    output=state.worker_summary,
                    cost_usd=result.get("api_cost"),
                    duration_seconds=state.worker_elapsed_seconds,
                )

        completion = check_mission_completion(seeded_mission_id)
        if completion.get("status") == "completed":
            mark_mission_completed(seeded_mission_id)
        elif completion.get("status") == "failed":
            mark_mission_failed(seeded_mission_id)

        log_event("seeded_mission_task_synced", {
            "task_id": task_id,
            "seeded_task_id": seeded_task_id,
            "seeded_mission_id": seeded_mission_id,
            "success": bool(result.get("success")),
            "mission_status": completion.get("status"),
        }, task_id=task_id)

    # ── Stale run watchdog ───────────────────────────────────────────────────
    if cfg.stale_run_watchdog_enabled:
        sw = evaluate_stale_run(
            last_task_completed_at=state.last_task_completed_at,
            loop_count=state.loop_count,
            max_stale_task_minutes=cfg.max_stale_task_minutes,
            warn_threshold_minutes=cfg.stale_run_warn_minutes,
        )
        if sw["stale"] and not state.stop_reason:
            state.stop_reason = sw["stop_reason"]
            log_event("loop_blocked_on_stale_run", {
                "task_id": task_id,
                "stale_minutes": sw["stale_minutes"],
                "max_stale_task_minutes": cfg.max_stale_task_minutes,
                "last_task_completed_at": state.last_task_completed_at,
            }, task_id=task_id)
        elif sw["warn"] and not state.stale_run_warning_sent:
            state.stale_run_warning_sent = True
            log_event("stale_run_warning", {
                "task_id": task_id,
                "stale_minutes": sw["stale_minutes"],
                "warn_threshold_minutes": cfg.stale_run_warn_minutes,
                "hard_stop_minutes": cfg.max_stale_task_minutes,
                "last_task_completed_at": state.last_task_completed_at,
            }, task_id=task_id)

    state.loop_count += 1
    state.current_task = None
    state.current_task_id = None
    state.current_worker = None
    state.current_branch = None
    state.worker_result = None
    state.worker_elapsed_seconds = None
    state.current_agent_run_id = None
    state.worker_summary = None
    state.check_passed = None
    state.deploy_result = None
    state.deploy_ready = None
    state.rollback_revert_status = None
    state.rollback_revert_plan = None
    state.resource_request_status = None
    state.acceptance_criteria_status = None
    state.definition_of_done_status = None
    state.code_review_status = None
    state.high_risk_review_status = None
    state.codex_escalation_status = None
    state.auto_repair_attempt = 0
    state.auto_repair_status = None
    state.check_output = None
    state.resolved_model = None
    state.context_compression = None
    state.merge_approval_status = None
    state.merge_risk_level = None
    state.e2e_result = None
    state.ui_flow_result = None
    state.product_eval_result = None
    return _persist(state, "update_logs_and_state")


def run_strategic_gate(state: RunnerState) -> RunnerState:
    """Strategic decision gate: pause the loop every N tasks for human review.

    When ``STRATEGIC_PAUSE_INTERVAL`` is set to N > 0, the loop pauses after
    every N completed task loops and writes a review request to ``outbox/``.
    The human creates an approval file in ``inbox/`` to resume.

    If the gate was already pending from a prior run (persisted in state), this
    node re-checks the inbox on each restart — so one additional task may run
    between the gate firing and the approval check on the next restart.  That
    is the inherent cost of a post-task gate; it is acceptable for review
    intervals of 5+ tasks.
    """
    if not cfg.strategic_gate_enabled or cfg.strategic_pause_interval <= 0:
        return state

    # Re-check a gate that fired in a prior run: look for the approval file.
    if state.strategic_gate_status == "pending":
        gate_loop = state.strategic_gate_at_loop or 0
        approved_path = _RUNNER_DIR / "inbox" / f"strategic_review_{gate_loop}_approved.txt"
        if approved_path.exists():
            state.strategic_gate_status = None
            state.strategic_gate_at_loop = None
            state.strategic_tasks_since_gate = 0
            log_event("strategic_gate_approved", {
                "gate_loop": gate_loop,
                "message": "Human approved strategic review; resuming autonomous run.",
            })
        else:
            state.stop_reason = STRATEGIC_GATE_STOP
            log_event("loop_blocked_on_strategic_gate", {
                "gate_loop": gate_loop,
                "message": f"Waiting for approval file: inbox/strategic_review_{gate_loop}_approved.txt",
            })
        return _persist(state, "run_strategic_gate")

    # Fresh evaluation: increment the counter and check whether the interval is reached.
    gate = evaluate_strategic_gate(
        tasks_since_gate=state.strategic_tasks_since_gate,
        strategic_pause_interval=cfg.strategic_pause_interval,
    )
    state.strategic_tasks_since_gate = gate["tasks_since_gate"]

    if gate["triggered"]:
        gate_loop = state.loop_count
        review_path = _RUNNER_DIR / "outbox" / f"strategic_review_{gate_loop}.txt"
        approved_path = _RUNNER_DIR / "inbox" / f"strategic_review_{gate_loop}_approved.txt"

        # Write the review request (idempotent — only on first encounter).
        if not review_path.exists():
            digest = state.worker_summary_digest or ""
            review_path.write_text(format_review_file(
                loop_count=gate_loop,
                tasks_since_gate=cfg.strategic_pause_interval,
                summary_digest=digest,
                inbox_filename=approved_path.name,
            ))

        if not approved_path.exists():
            state.strategic_gate_status = "pending"
            state.strategic_gate_at_loop = gate_loop
            state.stop_reason = STRATEGIC_GATE_STOP
            log_event("strategic_gate_triggered", {
                "loop_count": gate_loop,
                "tasks_since_gate": cfg.strategic_pause_interval,
                "review_path": str(review_path),
                "approve_by": str(approved_path),
                "message": (
                    f"Strategic review required after {cfg.strategic_pause_interval} tasks. "
                    f"See {review_path.name}; create {approved_path.name} to resume."
                ),
            })
        else:
            # Pre-approved (edge case: operator already created the file).
            log_event("strategic_gate_auto_approved", {"gate_loop": gate_loop})

    return _persist(state, "run_strategic_gate")


def ask_chatgpt_next_task(state: RunnerState) -> RunnerState:
    # If the loop is already flagged to stop (e.g. a deploy failed or timed out),
    # don't ask the planner for — or queue — another task that would never run.
    if state.stop_reason:
        return state
    # A failed task was just requeued for retry; let that retry run next loop
    # rather than piling a fresh planner task on top of it.
    if state.retry_pending:
        return state
    # In strict seeded queue mode the planner is never consulted: all tasks come
    # from Supabase missions and the loop stops when the queue is exhausted.
    if cfg.seeded_mission_queue_enabled and cfg.seeded_mission_queue_strict:
        return state
    # Don't ask the planner for a new task when the queue already has work. Tasks
    # in the queue came from a seeded mission or mission compiler batch — injecting
    # planner tasks on top disrupts batch ordering and can push the run past
    # MAX_LOOP_TASKS before the batch completes.
    if get_next_queued_task():
        return state
    summary_text = state.worker_summary_digest or build_run_summary_digest(state.worker_summary)
    planner = ChatGPTWorker()
    new_task = planner.ask_for_next_task(summary_text, completed_tasks=_completed_tasks())
    if new_task:
        new_task = guard_planner_task(
            new_task,
            context="ask_chatgpt_next_task",
            v2=cfg.planner_quality_gate_v2_enabled,
            scope_guard=cfg.planner_scope_guard_enabled,
        )
    if new_task:
        add_task(new_task)
        log_event("next_task_requested", {"new_task": new_task})
    else:
        # Check if there are still queued tasks before giving up
        if not get_next_queued_task():
            state.stop_reason = "no_more_tasks"
    return _persist(state, "ask_chatgpt_next_task")


def generate_live_batch_validation_report(state: RunnerState) -> RunnerState:
    """Final Live-Batch Validation Report.

    Runs once, immediately after the loop decides to stop, and emits a
    structured summary of the completed batch: task outcomes (complete /
    failed / blocked / queued), session health metrics (cost, loop count,
    stop reason, elapsed time), and a per-task digest of up to 50 entries.

    The report is written to outbox/live_batch_validation_report.txt and
    logged as ``live_batch_validation_complete`` (which also fires a Slack
    notification when that event is in the notify set).

    Skipped when ``LIVE_BATCH_VALIDATION_REPORT=false``.
    """
    if not cfg.live_batch_validation_report_enabled:
        return state

    session_state = {
        "stop_reason": state.stop_reason,
        "loop_count": state.loop_count,
        "session_cost": state.session_cost,
        "started_at": state.started_at,
        "consecutive_failures": state.consecutive_failures,
        "worker_timeout_count": state.worker_timeout_count,
    }

    result = generate_live_batch_report(
        session_state,
        context="generate_live_batch_validation_report",
    )

    state.live_batch_validation_result = result

    report_path = _RUNNER_DIR / "outbox" / "live_batch_validation_report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(result["report"])

    return _persist(state, "generate_live_batch_validation_report")


def decide_continue_or_stop(state: RunnerState) -> RunnerState:
    # ── Claude subscription cooldown auto-resume ─────────────────────────────
    # When the Claude subscription rate-limiter fired this iteration, sleep
    # until the cooldown expires before the next loop iteration so that
    # load_next_task finds the requeued task ready.  This check runs before the
    # stop_reason gate so a cooldown doesn't inadvertently stop the loop.
    cooldown_until = state.claude_subscription_cooldown_until
    if cooldown_until and not state.stop_reason:
        try:
            resume_dt = datetime.fromisoformat(cooldown_until)
            remaining = (resume_dt - datetime.utcnow()).total_seconds()
            if remaining > 0:
                # Treat the start of the wait as activity too, so
                # stale_run_watchdog can't trip on a gap it never saw
                # (the watchdog only checks in update_logs_and_state,
                # which won't run again until the wait is over).
                state.last_task_completed_at = datetime.utcnow().isoformat()
                log_event("claude_subscription_cooldown_waiting", {
                    "resume_at": cooldown_until,
                    "remaining_seconds": round(remaining, 1),
                })
                time.sleep(remaining)
                # Cooldown sleeps are excluded from MAX_RUNTIME_MINUTES (see
                # the effective-elapsed calculation below) and count as
                # activity for stale_run_watchdog purposes.
                state.cooldown_wait_seconds_total += remaining
                state.last_task_completed_at = datetime.utcnow().isoformat()
        except (ValueError, TypeError):
            pass
        state.claude_subscription_cooldown_until = None
        log_event("claude_subscription_cooldown_resumed", {
            "cooldown_count": state.claude_subscription_cooldown_count,
        })

    if state.stop_reason:
        state.status = "stopped"
        log_event("loop_stopped", {"reason": state.stop_reason})
        return state

    if state.loop_count >= cfg.max_loop_tasks:
        state.stop_reason = "max_loop_tasks"
        state.status = "stopped"
        log_event("loop_stopped", {"reason": "max_loop_tasks", "count": state.loop_count})
        return state

    started_at = state.started_at
    if started_at:
        from datetime import timezone
        elapsed = (datetime.utcnow() - datetime.fromisoformat(started_at)).total_seconds() / 60
        # Cooldown waits are wall-clock time the loop spent deliberately
        # asleep, not runtime the run actually used — exclude them so
        # sleeping through a Claude subscription reset window never
        # kills an otherwise-healthy run.
        effective_elapsed = elapsed - (state.cooldown_wait_seconds_total / 60)
        if effective_elapsed > cfg.max_runtime_minutes:
            state.stop_reason = "max_runtime"
            state.status = "stopped"
            log_event("loop_stopped", {
                "reason": "max_runtime",
                "elapsed_minutes": elapsed,
                "effective_elapsed_minutes": effective_elapsed,
                "cooldown_wait_seconds_total": state.cooldown_wait_seconds_total,
            })
            return state

    state.status = "running"
    return _persist(state, "decide_continue_or_stop")


# ── Routing ───────────────────────────────────────────────────────────────────

def _route_after_load(state: RunnerState) -> str:
    if state.stop_reason:
        return "compile_mission_if_needed"
    return "choose_worker"


def _route_after_compile_mission(state: RunnerState) -> str:
    if state.current_task:
        return "choose_worker"
    return "seed_mission_queue_if_needed"


def _route_after_seed_mission_queue(state: RunnerState) -> str:
    # Strict mode already set stop_reason="seeded_queue_exhausted" in
    # seed_mission_queue_if_needed; route straight to the stop check instead of
    # falling through to the ChatGPT planner, which strict mode must never consult.
    if state.stop_reason == "seeded_queue_exhausted":
        return "decide_continue_or_stop"
    if state.current_task:
        return "choose_worker"
    return "ask_chatgpt_for_task_if_needed"


def _route_after_chatgpt(state: RunnerState) -> str:
    if not state.current_task:
        state.status = "stopped"
        return "decide_continue_or_stop"
    return "choose_worker"


def _route_after_business_repo(state: RunnerState) -> str:
    if state.stop_reason:
        return "decide_continue_or_stop"
    return "check_acceptance_criteria"


def _route_after_acceptance_criteria(state: RunnerState) -> str:
    if state.acceptance_criteria_status == "failed":
        return "decide_continue_or_stop"
    return "resolve_model"


def _route_after_definition_of_done(state: RunnerState) -> str:
    if state.definition_of_done_status == "failed":
        return "decide_continue_or_stop"
    return "request_resources_if_needed"


def _route_after_code_review(state: RunnerState) -> str:
    if state.code_review_status == "failed":
        return "decide_continue_or_stop"
    return "check_high_risk_claude_review"


def _route_after_high_risk_review(state: RunnerState) -> str:
    if state.high_risk_review_status == "failed":
        return "decide_continue_or_stop"
    return "request_resources_if_needed"


def _route_after_resource_gate(state: RunnerState) -> str:
    # When the gate is awaiting human-provided resources it halts the loop:
    # skip commit/deploy/etc. and go straight to decide_continue_or_stop, which
    # ends the run cleanly on the stop_reason set in the node.
    if state.resource_request_status == "pending":
        return "decide_continue_or_stop"
    return "run_checks_if_needed"


def _route_after_merge_approval(state: RunnerState) -> str:
    if state.merge_approval_status == "pending":
        return "decide_continue_or_stop"
    return "commit_push_merge_if_needed"


def _route_after_strategic_gate(state: RunnerState) -> str:
    if state.strategic_gate_status == "pending":
        return "decide_continue_or_stop"
    return "ask_chatgpt_next_task"


def _route_after_decide(state: RunnerState) -> str:
    if state.status == "stopped":
        return "generate_live_batch_validation_report"
    return "load_next_task"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(RunnerState)

    builder.add_node("install_hooks", install_hooks)
    builder.add_node("check_launch_readiness_if_needed", check_launch_readiness_if_needed)
    builder.add_node("check_pending_migrations_if_needed", check_pending_migrations_if_needed)
    builder.add_node("load_next_task", load_next_task)
    builder.add_node("compile_mission_if_needed", compile_mission_if_needed)
    builder.add_node("seed_mission_queue_if_needed", seed_mission_queue_if_needed)
    builder.add_node("ask_chatgpt_for_task_if_needed", ask_chatgpt_for_task_if_needed)
    builder.add_node("choose_worker", choose_worker)
    builder.add_node("resolve_business_repo_if_needed", resolve_business_repo_if_needed)
    builder.add_node("check_acceptance_criteria", check_acceptance_criteria)
    builder.add_node("resolve_model", resolve_model_node)
    builder.add_node("generate_worker_prompt", generate_worker_prompt)
    builder.add_node("dispatch_worker", dispatch_worker)
    builder.add_node("capture_worker_result", capture_worker_result)
    builder.add_node("escalate_to_claude_if_needed", escalate_to_claude_if_needed)
    builder.add_node("parse_worker_summary", parse_worker_summary_node)
    builder.add_node("check_definition_of_done", check_definition_of_done)
    builder.add_node("check_independent_code_review", check_independent_code_review)
    builder.add_node("check_high_risk_claude_review", check_high_risk_claude_review)
    builder.add_node("request_resources_if_needed", request_resources_if_needed)
    builder.add_node("run_checks_if_needed", run_checks_if_needed)
    builder.add_node("auto_repair_if_needed", auto_repair_if_needed)
    builder.add_node("check_merge_approval_if_needed", check_merge_approval_if_needed)
    builder.add_node("commit_push_merge_if_needed", commit_push_merge_if_needed)
    builder.add_node("apply_sql_if_needed", apply_sql_if_needed)
    builder.add_node("deploy_if_needed", deploy_if_needed)
    builder.add_node("run_e2e_if_needed", run_e2e_if_needed)
    builder.add_node("run_ui_flow_validation_if_needed", run_ui_flow_validation_if_needed)
    builder.add_node("run_product_eval_if_needed", run_product_eval_if_needed)
    builder.add_node("update_github_if_needed", update_github_if_needed)
    builder.add_node("update_logs_and_state", update_logs_and_state)
    builder.add_node("run_strategic_gate", run_strategic_gate)
    builder.add_node("ask_chatgpt_next_task", ask_chatgpt_next_task)
    builder.add_node("decide_continue_or_stop", decide_continue_or_stop)
    builder.add_node("generate_live_batch_validation_report", generate_live_batch_validation_report)

    builder.set_entry_point("install_hooks")
    builder.add_edge("install_hooks", "check_launch_readiness_if_needed")
    builder.add_conditional_edges(
        "check_launch_readiness_if_needed",
        lambda s: "decide_continue_or_stop" if s.stop_reason == "launch_readiness_failed" else "check_pending_migrations_if_needed",
        {
            "check_pending_migrations_if_needed": "check_pending_migrations_if_needed",
            "decide_continue_or_stop": "decide_continue_or_stop",
        },
    )
    builder.add_edge("check_pending_migrations_if_needed", "load_next_task")

    builder.add_conditional_edges("load_next_task", _route_after_load, {
        "compile_mission_if_needed": "compile_mission_if_needed",
        "choose_worker": "choose_worker",
    })
    builder.add_conditional_edges("compile_mission_if_needed", _route_after_compile_mission, {
        "choose_worker": "choose_worker",
        "seed_mission_queue_if_needed": "seed_mission_queue_if_needed",
    })
    builder.add_conditional_edges("seed_mission_queue_if_needed", _route_after_seed_mission_queue, {
        "choose_worker": "choose_worker",
        "ask_chatgpt_for_task_if_needed": "ask_chatgpt_for_task_if_needed",
        "decide_continue_or_stop": "decide_continue_or_stop",
    })

    builder.add_conditional_edges("ask_chatgpt_for_task_if_needed", _route_after_chatgpt, {
        "decide_continue_or_stop": "decide_continue_or_stop",
        "choose_worker": "choose_worker",
    })
    builder.add_edge("choose_worker", "resolve_business_repo_if_needed")
    builder.add_conditional_edges("resolve_business_repo_if_needed", _route_after_business_repo, {
        "check_acceptance_criteria": "check_acceptance_criteria",
        "decide_continue_or_stop": "decide_continue_or_stop",
    })
    builder.add_conditional_edges("check_acceptance_criteria", _route_after_acceptance_criteria, {
        "resolve_model": "resolve_model",
        "decide_continue_or_stop": "decide_continue_or_stop",
    })
    builder.add_edge("resolve_model", "generate_worker_prompt")
    builder.add_edge("generate_worker_prompt", "dispatch_worker")
    builder.add_edge("dispatch_worker", "capture_worker_result")
    builder.add_edge("capture_worker_result", "escalate_to_claude_if_needed")
    builder.add_edge("escalate_to_claude_if_needed", "parse_worker_summary")
    builder.add_edge("parse_worker_summary", "check_definition_of_done")
    builder.add_conditional_edges("check_definition_of_done", _route_after_definition_of_done, {
        "decide_continue_or_stop": "decide_continue_or_stop",
        "request_resources_if_needed": "check_independent_code_review",
    })
    builder.add_conditional_edges("check_independent_code_review", _route_after_code_review, {
        "decide_continue_or_stop": "decide_continue_or_stop",
        "check_high_risk_claude_review": "check_high_risk_claude_review",
    })
    builder.add_conditional_edges("check_high_risk_claude_review", _route_after_high_risk_review, {
        "decide_continue_or_stop": "decide_continue_or_stop",
        "request_resources_if_needed": "request_resources_if_needed",
    })
    builder.add_conditional_edges("request_resources_if_needed", _route_after_resource_gate, {
        "decide_continue_or_stop": "decide_continue_or_stop",
        "run_checks_if_needed": "run_checks_if_needed",
    })
    builder.add_edge("run_checks_if_needed", "auto_repair_if_needed")
    builder.add_edge("auto_repair_if_needed", "check_merge_approval_if_needed")
    builder.add_conditional_edges("check_merge_approval_if_needed", _route_after_merge_approval, {
        "decide_continue_or_stop": "decide_continue_or_stop",
        "commit_push_merge_if_needed": "commit_push_merge_if_needed",
    })
    builder.add_edge("commit_push_merge_if_needed", "apply_sql_if_needed")
    builder.add_edge("apply_sql_if_needed", "deploy_if_needed")
    builder.add_edge("deploy_if_needed", "run_e2e_if_needed")
    builder.add_edge("run_e2e_if_needed", "run_ui_flow_validation_if_needed")
    builder.add_edge("run_ui_flow_validation_if_needed", "run_product_eval_if_needed")
    builder.add_edge("run_product_eval_if_needed", "update_github_if_needed")
    builder.add_edge("update_github_if_needed", "update_logs_and_state")
    builder.add_edge("update_logs_and_state", "run_strategic_gate")
    builder.add_conditional_edges("run_strategic_gate", _route_after_strategic_gate, {
        "ask_chatgpt_next_task": "ask_chatgpt_next_task",
        "decide_continue_or_stop": "decide_continue_or_stop",
    })
    builder.add_edge("ask_chatgpt_next_task", "decide_continue_or_stop")

    builder.add_conditional_edges("decide_continue_or_stop", _route_after_decide, {
        "generate_live_batch_validation_report": "generate_live_batch_validation_report",
        "load_next_task": "load_next_task",
    })
    builder.add_edge("generate_live_batch_validation_report", END)

    return builder.compile()


graph = build_graph()
