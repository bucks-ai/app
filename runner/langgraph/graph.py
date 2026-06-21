"""LangGraph StateGraph for the bucks.ai Autonomous Development Runner."""
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from state import RunnerState
from config import get_config
from tools.log_tools import log_event, update_state
from tools.task_tools import (
    get_next_queued_task,
    mark_task_running,
    mark_task_complete,
    mark_task_failed,
    mark_task_blocked,
    requeue_task,
    add_task,
    update_task_branch,
)
from tools.failure_guard import evaluate_failure
from tools.repeated_error_guard import evaluate_error_repetition, evaluate_task_repetition
from tools.worker_timeout_guard import evaluate_worker_timeout
from tools.codex_usage_limit_guard import evaluate_codex_usage_limit
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
)
from tools.sql_guard import scan_sql_text
from tools.supabase_tools import apply_sql_file
from tools.vercel_tools import trigger_deploy
from tools.github_tools import sync_open_issues_to_tasks
from tools.task_quality_guard import guard_planner_task
from tools.claude_hooks_safety_pack import write_hooks
from tools.acceptance_criteria_gate import guard_acceptance_criteria
from tools.definition_of_done import guard_definition_of_done
from tools.independent_code_review import guard_code_review, get_diff_text
from tools.high_risk_claude_review import guard_high_risk_claude_review
from tools.strategic_decision_gate import (
    evaluate_strategic_gate,
    format_review_file,
    STRATEGIC_GATE_STOP,
)
from tools.model_routing_policy import evaluate_model_routing_policy
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


def _state_dict(state: RunnerState) -> dict:
    return state.model_dump()


def _persist(state: RunnerState, step: str) -> RunnerState:
    state.last_completed_step = step
    state.updated_at = datetime.utcnow().isoformat()
    update_state(_state_dict(state))
    return state


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
    Skipped when the safety pack or auto-install is disabled.
    """
    if not cfg.claude_hooks_safety_pack_enabled or not cfg.claude_hooks_safety_pack_auto_install:
        return state

    result = write_hooks(cfg.repo_path)
    log_event("claude_hooks_installed", {
        "path": result["path"],
        "wrote": result["wrote"],
        "merged": result["merged"],
    })
    return _persist(state, "install_hooks")


def load_next_task(state: RunnerState) -> RunnerState:
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
    summary_text = state.worker_summary_digest or build_run_summary_digest(state.worker_summary)
    log_event("next_task_requested", {"summary_preview": summary_text[:200]})
    planner = ChatGPTWorker()
    new_task = planner.ask_for_next_task(summary_text)
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
    preferred = task.get("preferred_worker", "").lower()
    task_type = task.get("type", "").lower()

    if preferred in ("claude", "codex"):
        state.current_worker = preferred
    elif task_type in ("ui", "frontend", "polish", "design"):
        state.current_worker = "codex"
    else:
        state.current_worker = "claude"

    log_event("worker_started", {"worker": state.current_worker, "task_id": state.current_task_id})
    return _persist(state, "choose_worker")


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
    return _persist(state, "resolve_model")


def generate_worker_prompt(state: RunnerState) -> RunnerState:
    state = _compress_context_if_needed(state, reason="before_worker_prompt")
    task = state.current_task or {}
    prompt = _TASK_PROMPT_TEMPLATE.format(
        repo_path=cfg.repo_path,
        title=task.get("title", ""),
        type=task.get("type", "general"),
        branch=task.get("branch", f"feature/{task.get('id', 'task')}"),
    )
    state.messages = state.messages + [{"role": "user", "content": prompt}]
    log_event("prompt_generated", {"task_id": state.current_task_id, "prompt_len": len(prompt)})
    return _persist(state, "generate_worker_prompt")


def dispatch_worker(state: RunnerState) -> RunnerState:
    task = state.current_task or {}
    if state.resolved_model:
        task = dict(task)
        task["resolved_model"] = state.resolved_model
    prompt = (state.messages[-1]["content"] if state.messages else "")
    mark_task_running(task.get("id", ""))

    if state.current_worker == "codex":
        worker = CodexWorker()
    else:
        worker = ClaudeWorker()

    _start = time.monotonic()
    result = worker.run_worker_prompt(prompt, task)
    state.worker_elapsed_seconds = round(time.monotonic() - _start, 2)
    state.worker_result = result.model_dump()
    log_event("worker_finished", {"worker": state.current_worker, "success": result.success, "elapsed_seconds": state.worker_elapsed_seconds, "task_id": state.current_task_id})
    return _persist(state, "dispatch_worker")


def capture_worker_result(state: RunnerState) -> RunnerState:
    result = state.worker_result or {}
    output = result.get("output") or ""
    if output:
        state.messages = state.messages + [{"role": "assistant", "content": output}]
    log_event("summary_captured", {"task_id": state.current_task_id, "output_len": len(output)})
    return _persist(state, "capture_worker_result")


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

    decision = guard_definition_of_done(
        summary=summary,
        task=task,
        raw_output=raw_output,
        context="check_definition_of_done",
        strict_mode=cfg.definition_of_done_strict_mode,
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
    diff_text = get_diff_text(cfg.repo_path)

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
    diff_text = get_diff_text(cfg.repo_path)

    decision = guard_high_risk_claude_review(
        diff_text=diff_text,
        summary=summary,
        task=task,
        context="check_high_risk_claude_review",
        strict_mode=cfg.high_risk_claude_review_strict_mode,
        model=cfg.high_risk_claude_review_model,
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
    check = run_check(cfg.repo_path)
    state.check_passed = check["success"]
    return _persist(state, "run_checks_if_needed")


def commit_push_merge_if_needed(state: RunnerState) -> RunnerState:
    task = state.current_task or {}
    result = state.worker_result or {}
    if not result.get("success") or not state.check_passed:
        return state

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

    br = create_branch(cfg.repo_path, branch)
    if not br["success"]:
        return state

    state.current_branch = branch
    task_title = task.get("title", "runner task")
    commit = commit_all(cfg.repo_path, f"Complete: {task_title}")
    # A commit "landed" either when the runner created one, or when the worker had
    # already committed its own changes (clean tree -> "nothing to commit"). In both
    # cases HEAD is deployable, so record it and run push/merge — otherwise
    # deploy_if_needed wrongly skips with "no committed changes to deploy".
    if commit.get("committed"):
        state.last_commit = commit["sha"]
        push_branch(cfg.repo_path, branch)

        if cfg.auto_merge:
            merge = merge_feature_branch(cfg.repo_path, branch)
            if merge.get("success"):
                fetch_pull_main(cfg.repo_path)
                if cfg.auto_cleanup_branches:
                    cleanup_feature_branch(cfg.repo_path, branch)

    return _persist(state, "commit_push_merge_if_needed")


_RUNNER_DIR = Path(__file__).parent


def apply_sql_if_needed(state: RunnerState) -> RunnerState:
    summary = state.worker_summary or {}
    sql_required = summary.get("sql_required")
    sql_file = summary.get("sql_file_path")

    if not sql_required or not sql_file:
        return state

    # SQL approval gate: when REQUIRE_SQL_APPROVAL=true, write SQL to outbox for
    # human review and only proceed once the human writes an approval file to inbox.
    if cfg.require_sql_approval:
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

        if cfg.failure_guard_enabled:
            decision = evaluate_failure(
                task,
                state.consecutive_failures,
                max_task_retries=cfg.max_task_retries,
                max_consecutive_failures=cfg.max_consecutive_failures,
            )
            state.consecutive_failures = decision["consecutive_failures"]

            if decision["action"] == "retry":
                # Transient failure: requeue the task for another attempt instead
                # of abandoning it. It keeps its place in the queue, so
                # load_next_task picks it up again next loop.
                requeue_task(task_id, decision["retry_count"])
                state.retry_pending = True
                log_event("task_retry_scheduled", {
                    "task_id": task_id,
                    "error": err,
                    "attempt": decision["retry_count"],
                    "max_retries": cfg.max_task_retries,
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
        else:
            _sync_err = result.get("error") or "worker returned no output"
            mark_seeded_task_failed(seeded_task_id, _sync_err[:500])

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

    state.loop_count += 1
    state.current_task = None
    state.worker_result = None
    state.worker_elapsed_seconds = None
    state.check_passed = None
    state.deploy_result = None
    state.deploy_ready = None
    state.rollback_revert_status = None
    state.rollback_revert_plan = None
    state.resource_request_status = None
    state.code_review_status = None
    state.high_risk_review_status = None
    state.resolved_model = None
    state.context_compression = None
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
    summary_text = state.worker_summary_digest or build_run_summary_digest(state.worker_summary)
    planner = ChatGPTWorker()
    new_task = planner.ask_for_next_task(summary_text)
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


def decide_continue_or_stop(state: RunnerState) -> RunnerState:
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
        if elapsed > cfg.max_runtime_minutes:
            state.stop_reason = "max_runtime"
            state.status = "stopped"
            log_event("loop_stopped", {"reason": "max_runtime", "elapsed_minutes": elapsed})
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
    if state.current_task:
        return "choose_worker"
    return "ask_chatgpt_for_task_if_needed"


def _route_after_chatgpt(state: RunnerState) -> str:
    if not state.current_task:
        state.status = "stopped"
        return "decide_continue_or_stop"
    return "choose_worker"


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


def _route_after_strategic_gate(state: RunnerState) -> str:
    if state.strategic_gate_status == "pending":
        return "decide_continue_or_stop"
    return "ask_chatgpt_next_task"


def _route_after_decide(state: RunnerState) -> str:
    if state.status == "stopped":
        return END
    return "load_next_task"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(RunnerState)

    builder.add_node("install_hooks", install_hooks)
    builder.add_node("load_next_task", load_next_task)
    builder.add_node("compile_mission_if_needed", compile_mission_if_needed)
    builder.add_node("seed_mission_queue_if_needed", seed_mission_queue_if_needed)
    builder.add_node("ask_chatgpt_for_task_if_needed", ask_chatgpt_for_task_if_needed)
    builder.add_node("choose_worker", choose_worker)
    builder.add_node("check_acceptance_criteria", check_acceptance_criteria)
    builder.add_node("resolve_model", resolve_model_node)
    builder.add_node("generate_worker_prompt", generate_worker_prompt)
    builder.add_node("dispatch_worker", dispatch_worker)
    builder.add_node("capture_worker_result", capture_worker_result)
    builder.add_node("parse_worker_summary", parse_worker_summary_node)
    builder.add_node("check_definition_of_done", check_definition_of_done)
    builder.add_node("check_independent_code_review", check_independent_code_review)
    builder.add_node("check_high_risk_claude_review", check_high_risk_claude_review)
    builder.add_node("request_resources_if_needed", request_resources_if_needed)
    builder.add_node("run_checks_if_needed", run_checks_if_needed)
    builder.add_node("commit_push_merge_if_needed", commit_push_merge_if_needed)
    builder.add_node("apply_sql_if_needed", apply_sql_if_needed)
    builder.add_node("deploy_if_needed", deploy_if_needed)
    builder.add_node("update_github_if_needed", update_github_if_needed)
    builder.add_node("update_logs_and_state", update_logs_and_state)
    builder.add_node("run_strategic_gate", run_strategic_gate)
    builder.add_node("ask_chatgpt_next_task", ask_chatgpt_next_task)
    builder.add_node("decide_continue_or_stop", decide_continue_or_stop)

    builder.set_entry_point("install_hooks")
    builder.add_edge("install_hooks", "load_next_task")

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
    })

    builder.add_conditional_edges("ask_chatgpt_for_task_if_needed", _route_after_chatgpt, {
        "decide_continue_or_stop": "decide_continue_or_stop",
        "choose_worker": "choose_worker",
    })
    builder.add_edge("choose_worker", "check_acceptance_criteria")
    builder.add_conditional_edges("check_acceptance_criteria", _route_after_acceptance_criteria, {
        "resolve_model": "resolve_model",
        "decide_continue_or_stop": "decide_continue_or_stop",
    })
    builder.add_edge("resolve_model", "generate_worker_prompt")
    builder.add_edge("generate_worker_prompt", "dispatch_worker")
    builder.add_edge("dispatch_worker", "capture_worker_result")
    builder.add_edge("capture_worker_result", "parse_worker_summary")
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
    builder.add_edge("run_checks_if_needed", "commit_push_merge_if_needed")
    builder.add_edge("commit_push_merge_if_needed", "apply_sql_if_needed")
    builder.add_edge("apply_sql_if_needed", "deploy_if_needed")
    builder.add_edge("deploy_if_needed", "update_github_if_needed")
    builder.add_edge("update_github_if_needed", "update_logs_and_state")
    builder.add_edge("update_logs_and_state", "run_strategic_gate")
    builder.add_conditional_edges("run_strategic_gate", _route_after_strategic_gate, {
        "ask_chatgpt_next_task": "ask_chatgpt_next_task",
        "decide_continue_or_stop": "decide_continue_or_stop",
    })
    builder.add_edge("ask_chatgpt_next_task", "decide_continue_or_stop")

    builder.add_conditional_edges("decide_continue_or_stop", _route_after_decide, {
        END: END,
        "load_next_task": "load_next_task",
    })

    return builder.compile()


graph = build_graph()
