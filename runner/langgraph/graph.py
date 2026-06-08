"""LangGraph StateGraph for the bucks.ai Autonomous Development Runner."""
import sys
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
    add_task,
    update_task_branch,
)
from tools.summary_tools import parse_worker_summary
from tools.git_tools import (
    create_branch,
    run_check,
    commit_all,
    push_branch,
    merge_feature_branch,
    fetch_pull_main,
    push_deploy_if_available,
    current_branch,
)
from tools.sql_guard import scan_sql_text
from tools.supabase_tools import apply_sql_file
from tools.vercel_tools import trigger_deploy
from tools.github_tools import create_or_update_task_from_issue
from tools.task_quality_guard import guard_planner_task
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


# ── Nodes ────────────────────────────────────────────────────────────────────

def load_next_task(state: RunnerState) -> RunnerState:
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


def ask_chatgpt_for_task_if_needed(state: RunnerState) -> RunnerState:
    if state.current_task:
        return state
    summary = state.worker_summary or {}
    summary_text = str(summary)
    log_event("next_task_requested", {"summary_preview": summary_text[:200]})
    planner = ChatGPTWorker()
    new_task = planner.ask_for_next_task(summary_text)
    if new_task:
        new_task = guard_planner_task(new_task, context="ask_chatgpt_for_task_if_needed")
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


def generate_worker_prompt(state: RunnerState) -> RunnerState:
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
    prompt = (state.messages[-1]["content"] if state.messages else "")
    mark_task_running(task.get("id", ""))

    if state.current_worker == "codex":
        worker = CodexWorker()
    else:
        worker = ClaudeWorker()

    result = worker.run_worker_prompt(prompt, task)
    state.worker_result = result.model_dump()
    log_event("worker_finished", {"worker": state.current_worker, "success": result.success, "task_id": state.current_task_id})
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
    state.worker_summary = summary
    return _persist(state, "parse_worker_summary")


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
    if commit["success"]:
        state.last_commit = commit["sha"]
        push_branch(cfg.repo_path, branch)

        if cfg.auto_merge:
            merge_feature_branch(cfg.repo_path, branch)
            fetch_pull_main(cfg.repo_path)

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


def update_github_if_needed(state: RunnerState) -> RunnerState:
    if not cfg.has_github:
        return state
    summary = state.worker_summary or {}
    task = state.current_task or {}
    issue_number = task.get("issue_number")
    if issue_number:
        from tools.github_tools import comment_issue
        repo = f"arnavt687/bucks-ai"
        comment_issue(repo, issue_number, f"Runner completed task: {task.get('title')}\n\nSummary: {str(summary)[:500]}")
    return _persist(state, "update_github_if_needed")


def update_logs_and_state(state: RunnerState) -> RunnerState:
    task = state.current_task or {}
    result = state.worker_result or {}
    task_id = task.get("id", "")

    if result.get("success"):
        mark_task_complete(task_id, str(state.worker_summary or "")[:500])
        log_event("task_completed", {"task_id": task_id}, task_id=task_id)
    else:
        err = result.get("error") or "worker returned no output"
        mark_task_failed(task_id, err)
        log_event("error", {"task_id": task_id, "error": err})

    state.loop_count += 1
    state.current_task = None
    state.worker_result = None
    state.check_passed = None
    return _persist(state, "update_logs_and_state")


def ask_chatgpt_next_task(state: RunnerState) -> RunnerState:
    summary_text = str(state.worker_summary or {})
    planner = ChatGPTWorker()
    new_task = planner.ask_for_next_task(summary_text)
    if new_task:
        new_task = guard_planner_task(new_task, context="ask_chatgpt_next_task")
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
        return "ask_chatgpt_for_task_if_needed"
    return "choose_worker"


def _route_after_chatgpt(state: RunnerState) -> str:
    if not state.current_task:
        state.status = "stopped"
        return "decide_continue_or_stop"
    return "choose_worker"


def _route_after_decide(state: RunnerState) -> str:
    if state.status == "stopped":
        return END
    return "load_next_task"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(RunnerState)

    builder.add_node("load_next_task", load_next_task)
    builder.add_node("ask_chatgpt_for_task_if_needed", ask_chatgpt_for_task_if_needed)
    builder.add_node("choose_worker", choose_worker)
    builder.add_node("generate_worker_prompt", generate_worker_prompt)
    builder.add_node("dispatch_worker", dispatch_worker)
    builder.add_node("capture_worker_result", capture_worker_result)
    builder.add_node("parse_worker_summary", parse_worker_summary_node)
    builder.add_node("run_checks_if_needed", run_checks_if_needed)
    builder.add_node("commit_push_merge_if_needed", commit_push_merge_if_needed)
    builder.add_node("apply_sql_if_needed", apply_sql_if_needed)
    builder.add_node("update_github_if_needed", update_github_if_needed)
    builder.add_node("update_logs_and_state", update_logs_and_state)
    builder.add_node("ask_chatgpt_next_task", ask_chatgpt_next_task)
    builder.add_node("decide_continue_or_stop", decide_continue_or_stop)

    builder.set_entry_point("load_next_task")

    builder.add_conditional_edges("load_next_task", _route_after_load, {
        "ask_chatgpt_for_task_if_needed": "ask_chatgpt_for_task_if_needed",
        "choose_worker": "choose_worker",
    })

    builder.add_conditional_edges("ask_chatgpt_for_task_if_needed", _route_after_chatgpt, {
        "decide_continue_or_stop": "decide_continue_or_stop",
        "choose_worker": "choose_worker",
    })
    builder.add_edge("choose_worker", "generate_worker_prompt")
    builder.add_edge("generate_worker_prompt", "dispatch_worker")
    builder.add_edge("dispatch_worker", "capture_worker_result")
    builder.add_edge("capture_worker_result", "parse_worker_summary")
    builder.add_edge("parse_worker_summary", "run_checks_if_needed")
    builder.add_edge("run_checks_if_needed", "commit_push_merge_if_needed")
    builder.add_edge("commit_push_merge_if_needed", "apply_sql_if_needed")
    builder.add_edge("apply_sql_if_needed", "update_github_if_needed")
    builder.add_edge("update_github_if_needed", "update_logs_and_state")
    builder.add_edge("update_logs_and_state", "ask_chatgpt_next_task")
    builder.add_edge("ask_chatgpt_next_task", "decide_continue_or_stop")

    builder.add_conditional_edges("decide_continue_or_stop", _route_after_decide, {
        END: END,
        "load_next_task": "load_next_task",
    })

    return builder.compile()


graph = build_graph()
