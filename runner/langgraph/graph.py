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
from tools.summary_tools import parse_worker_summary
from tools.resource_gate import collect_requests, evaluate_gate, format_request_file
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
    state.worker_summary = summary
    return _persist(state, "parse_worker_summary")


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

    return _persist(state, "deploy_if_needed")


def update_github_if_needed(state: RunnerState) -> RunnerState:
    if not cfg.has_github:
        return state
    summary = state.worker_summary or {}
    task = state.current_task or {}
    issue_number = task.get("issue_number")
    if issue_number:
        from tools.github_tools import comment_issue
        repo = f"arnavt687/bucks-ai"
        body = f"Runner completed task: {task.get('title')}\n\nSummary: {str(summary)[:500]}"
        if state.deploy_result is not None:
            poll = (state.deploy_result or {}).get("poll") or {}
            verdict = "ready" if state.deploy_ready else (poll.get("state") or "not ready")
            body += f"\n\nDeploy: {verdict}"
        comment_issue(repo, issue_number, body)
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
        mark_task_complete(task_id, str(state.worker_summary or "")[:500])
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

    state.loop_count += 1
    state.current_task = None
    state.worker_result = None
    state.worker_elapsed_seconds = None
    state.check_passed = None
    state.deploy_result = None
    state.deploy_ready = None
    state.resource_request_status = None
    return _persist(state, "update_logs_and_state")


def ask_chatgpt_next_task(state: RunnerState) -> RunnerState:
    # If the loop is already flagged to stop (e.g. a deploy failed or timed out),
    # don't ask the planner for — or queue — another task that would never run.
    if state.stop_reason:
        return state
    # A failed task was just requeued for retry; let that retry run next loop
    # rather than piling a fresh planner task on top of it.
    if state.retry_pending:
        return state
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


def _route_after_resource_gate(state: RunnerState) -> str:
    # When the gate is awaiting human-provided resources it halts the loop:
    # skip commit/deploy/etc. and go straight to decide_continue_or_stop, which
    # ends the run cleanly on the stop_reason set in the node.
    if state.resource_request_status == "pending":
        return "decide_continue_or_stop"
    return "run_checks_if_needed"


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
    builder.add_node("request_resources_if_needed", request_resources_if_needed)
    builder.add_node("run_checks_if_needed", run_checks_if_needed)
    builder.add_node("commit_push_merge_if_needed", commit_push_merge_if_needed)
    builder.add_node("apply_sql_if_needed", apply_sql_if_needed)
    builder.add_node("deploy_if_needed", deploy_if_needed)
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
    builder.add_edge("parse_worker_summary", "request_resources_if_needed")
    builder.add_conditional_edges("request_resources_if_needed", _route_after_resource_gate, {
        "decide_continue_or_stop": "decide_continue_or_stop",
        "run_checks_if_needed": "run_checks_if_needed",
    })
    builder.add_edge("run_checks_if_needed", "commit_push_merge_if_needed")
    builder.add_edge("commit_push_merge_if_needed", "apply_sql_if_needed")
    builder.add_edge("apply_sql_if_needed", "deploy_if_needed")
    builder.add_edge("deploy_if_needed", "update_github_if_needed")
    builder.add_edge("update_github_if_needed", "update_logs_and_state")
    builder.add_edge("update_logs_and_state", "ask_chatgpt_next_task")
    builder.add_edge("ask_chatgpt_next_task", "decide_continue_or_stop")

    builder.add_conditional_edges("decide_continue_or_stop", _route_after_decide, {
        END: END,
        "load_next_task": "load_next_task",
    })

    return builder.compile()


graph = build_graph()
