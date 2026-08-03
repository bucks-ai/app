"""Loop-stop diagnostics — every stop names its cause and its fix (M4c.0).

A bare stop reason (``stale_run``, ``chatgpt_no_task``, ``awaiting_resources``)
says *which guard fired*, not what happened or what to do about it. Recovering
that meant grepping ``logs/runs.jsonl`` and reading ``graph.py`` — and twice the
reconstruction landed on the wrong cause entirely:

  - ``chatgpt_no_task`` read as a broken planner when the real state was a
    strict-mode seeded queue with nothing left in it.
  - ``stale_run`` read as a hang when the watchdog was measuring against a
    4106-minute-old ``last_task_completed_at`` left over from a previous
    session.

Both misreads share a shape: the stop reason was reported without the numbers
that produced it. So every handler here prints the *observed* value next to the
*configured* threshold (``stale_minutes`` vs ``MAX_STALE_TASK_MINUTES``, both
labelled), quotes the five events immediately before the stop, and states a
CAUSE sentence and a RECOMMENDED ACTION naming the exact command or config
change that resolves it.

Two consumers:

  - the founder, via ``outbox/loop_stop_report.txt`` and one Slack message;
  - m4c-06's watchdog, via ``classification``: EXPECTED means the run finished
    the way it was configured to (safe to auto-restart or leave alone),
    ANOMALOUS means it broke (a human should look before it runs again).

Registry, not conditionals: ``STOP_HANDLERS`` maps every stop reason the runner
can set to its cause/action text. ``tests/test_stop_diagnostics.py`` scans
``graph.py`` and ``tools/*.py`` for stop reasons and fails on any that is
missing here — so a new stop reason cannot ship without its diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from tools.log_tools import log_event, read_logs

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

EXPECTED = "EXPECTED"
ANOMALOUS = "ANOMALOUS"

STOP_REPORT_EVENT = "loop_stop_report"
STOP_REPORT_FILENAME = "loop_stop_report.txt"

#: Used when the loop reaches the stop path with no ``stop_reason`` recorded.
UNSPECIFIED_STOP = "unspecified"

RECENT_EVENT_COUNT = 5

# How far back to look for the preceding events and for a handler's evidence
# event. Deep enough to survive a chatty final task loop, cheap to read.
_EVENT_SCAN_DEPTH = 400

# Events emitted by the shutdown reporting path itself. They are not "what
# happened before the stop" — quoting them would spend the five slots on this
# module's own output.
_REPORTING_EVENTS = frozenset({
    STOP_REPORT_EVENT,
    "live_batch_validation_complete",
    "slack_degraded",
})

#: Stops that mean "the run finished the way it was told to", not "the run
#: broke". The three named in the mission brief (seeded_queue_exhausted,
#: max_loop_tasks, cooldown) plus the two empty-queue stops that
#: ``main.py`` dry-run already treats as expected completions — an empty
#: queue is a finished batch, and restarting into it just stops again.
EXPECTED_STOP_REASONS = frozenset({
    "seeded_queue_exhausted",
    "max_loop_tasks",
    "claude_subscription_cooldown",
    "no_more_tasks",
    "no_queued_tasks",
})

# Config keys whose env var name is not simply the upper-cased key.
_ENV_NAME_OVERRIDES = {
    "repo_path": "BUCKS_AI_REPO_PATH",
    "resource_gate_enabled": "RESOURCE_GATE",
    "failure_guard_enabled": "FAILURE_GUARD",
    "worker_timeout_guard_enabled": "WORKER_TIMEOUT_GUARD",
    "cost_budget_guard_enabled": "COST_BUDGET_GUARD",
    "codex_usage_limit_guard_enabled": "CODEX_USAGE_LIMIT_GUARD",
    "strategic_gate_enabled": "STRATEGIC_GATE",
    "mission_compiler_enabled": "MISSION_COMPILER",
    "seeded_mission_queue_enabled": "SEEDED_MISSION_QUEUE",
    "startup_preflight_enabled": "STARTUP_PREFLIGHT",
    "worker_health_probe_enabled": "WORKER_HEALTH_PROBE",
    "worker_health_live_ping_enabled": "WORKER_HEALTH_LIVE_PING",
    "stale_run_watchdog_enabled": "STALE_RUN_WATCHDOG",
    "claude_subscription_cooldown_enabled": "CLAUDE_SUBSCRIPTION_COOLDOWN",
    "planner_quality_gate_v2_enabled": "PLANNER_QUALITY_GATE_V2",
    "planner_scope_guard_enabled": "PLANNER_SCOPE_GUARD",
}

# Never render a config value whose key looks like a credential. The handler
# table only names thresholds and policies, but this report is written to a
# file and posted to Slack, so the rule is enforced here rather than trusted.
_SECRET_KEY_MARKERS = ("key", "token", "secret", "password", "webhook", "dsn", "credential")

_REDACTED = "[redacted]"

# gate_authority stamps every gate block with these bookkeeping fields. They say
# which authority the gate consulted, not what was observed, so they are kept out
# of the "observed at the stop" list.
_OBSERVED_NOISE_KEYS = frozenset({
    "gate", "authority", "authority_external", "gate_assesses",
    "gate_block_policy", "message", "task_id",
})


def env_name_for(config_key: str) -> str:
    """Return the ``.env`` variable name that sets ``config_key``."""
    return _ENV_NAME_OVERRIDES.get(config_key, config_key.upper())


def is_secret_key(config_key: str) -> bool:
    return any(marker in config_key.lower() for marker in _SECRET_KEY_MARKERS)


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StopHandler:
    """Everything needed to explain one stop reason.

    ``cause`` and ``action`` are ``str.format_map`` templates. Placeholders are
    resolved against the merged context of config values, evidence pulled from
    the stop's own log events, and session state; anything unresolved renders
    as ``unknown`` rather than raising.
    """

    reason: str
    headline: str
    cause: str
    action: str
    #: Config keys printed alongside the stop, by ``cfg.report()`` key name.
    config_keys: tuple[str, ...] = ()
    #: Log events carrying the observed numbers; the most recent match wins.
    evidence_events: tuple[str, ...] = ()
    #: For gates that share the generic ``gate_blocked`` event, the
    #: ``gate_authority`` name that disambiguates which one fired.
    gate: Optional[str] = None


def _h(handler: StopHandler) -> tuple[str, StopHandler]:
    return handler.reason, handler


STOP_HANDLERS: dict[str, StopHandler] = dict([
    # ── Queue exhaustion — the run simply ran out of work ────────────────────
    _h(StopHandler(
        reason="no_queued_tasks",
        headline="The task queue was empty and nothing refilled it",
        cause=(
            "The local queue had no task in status 'queued', and none of the three "
            "sources produced one: the mission compiler found no YAML in inbox/, the "
            "seeded mission queue returned no queued mission, and the planner either "
            "was not consulted or returned nothing. There was no work to do — this is "
            "an empty queue, not a failure."
        ),
        action=(
            "Queue work, then re-run `python main.py run-loop`: drop a mission YAML in "
            "runner/langgraph/inbox/, or insert a missions row with status='queued' in "
            "Supabase. If you believe there IS work queued, the queue is mis-shaped, "
            "not empty — run `python main.py doctor` (add --fix to repair orphaned or "
            "duplicated tasks)."
        ),
        config_keys=(
            "mission_compiler_enabled",
            "seeded_mission_queue_enabled",
            "seeded_mission_queue_strict",
        ),
    )),
    _h(StopHandler(
        reason="no_more_tasks",
        headline="The planner had no follow-up task and the queue was empty",
        cause=(
            "After the last task loop the planner was asked for a follow-up task and "
            "returned nothing, and no queued task remained. The run finished the work "
            "it was given."
        ),
        action=(
            "Nothing is broken. Queue the next batch (mission YAML in "
            "runner/langgraph/inbox/, or a Supabase missions row with status='queued') "
            "and run `python main.py run-loop` again."
        ),
        config_keys=("chatgpt_model", "seeded_mission_queue_enabled", "max_loop_tasks"),
        evidence_events=("next_task_requested",),
    )),
    _h(StopHandler(
        reason="seeded_queue_exhausted",
        headline="Strict seeded-queue mode: no queued mission left in Supabase",
        cause=(
            "SEEDED_MISSION_QUEUE_STRICT is on, so the planner is never consulted and "
            "every task must come from a Supabase mission. No missions row is in status "
            "'queued', so every seeded mission has already been picked up. This is the "
            "designed end of a strict batch."
        ),
        action=(
            "Queue the next mission (insert a missions row with status='queued', or "
            "re-run the seeder e.g. `python seed_m4c0.py`), then `python main.py "
            "run-loop`. To let the planner generate work instead, set "
            "SEEDED_MISSION_QUEUE_STRICT=false."
        ),
        config_keys=("seeded_mission_queue_enabled", "seeded_mission_queue_strict"),
        evidence_events=("seeded_queue_exhausted",),
    )),
    _h(StopHandler(
        reason="chatgpt_no_task",
        headline="The planner returned no usable task",
        cause=(
            "The queue was empty so the planner was asked for a task, and it returned "
            "nothing — or returned one the planner quality/scope guard rejected. Read "
            "the config below before blaming the planner: this stop has been "
            "misdiagnosed as a planner fault when the real state was 'the seeded "
            "mission queue is empty', which is a queueing problem, not a planning one."
        ),
        action=(
            "Check the queue first: `python main.py doctor`. If every seeded mission is "
            "done, queue another mission instead of debugging the planner. If work IS "
            "queued but the planner still refused, look for task_quality_rejected in "
            "`python main.py logs` and check OPENAI_API_KEY / CHATGPT_MODEL are set."
        ),
        config_keys=(
            "chatgpt_model",
            "planner_quality_gate_v2_enabled",
            "planner_scope_guard_enabled",
            "seeded_mission_queue_enabled",
            "seeded_mission_queue_strict",
        ),
        evidence_events=("task_quality_rejected", "next_task_requested"),
    )),

    # ── Budgets ─────────────────────────────────────────────────────────────
    _h(StopHandler(
        reason="max_loop_tasks",
        headline="The batch ran its full task budget",
        cause=(
            "The run completed {loop_count} task loop(s), reaching MAX_LOOP_TASKS "
            "({max_loop_tasks}). This is the configured size of a batch, not a failure."
        ),
        action=(
            "Start the next batch with `python main.py run-loop` — a restart resets "
            "loop_count. To run longer batches, raise MAX_LOOP_TASKS in .env (keep "
            "MAX_RUNTIME_MINUTES large enough for the extra tasks)."
        ),
        config_keys=("max_loop_tasks", "max_runtime_minutes"),
    )),
    _h(StopHandler(
        reason="max_runtime",
        headline="The session ran out of wall-clock budget",
        cause=(
            "Effective runtime passed MAX_RUNTIME_MINUTES ({max_runtime_minutes} min); "
            "cooldown sleeps are already excluded from that budget. Hitting the clock "
            "before MAX_LOOP_TASKS ({max_loop_tasks}) means tasks ran slower than the "
            "batch was sized for."
        ),
        action=(
            "Compare effective_elapsed_minutes below against MAX_RUNTIME_MINUTES. If "
            "the work legitimately needs longer, raise MAX_RUNTIME_MINUTES in .env "
            "(it must stay above MAX_STALE_TASK_MINUTES = {max_stale_task_minutes}). If "
            "one task ate the window, look at WORKER_TIMEOUT_THRESHOLD "
            "({worker_timeout_threshold}s) and CLAUDE_CLI_TIMEOUT_S "
            "({claude_cli_timeout_s}s) — a worker that hangs to its ceiling burns the "
            "runtime budget without producing anything."
        ),
        config_keys=(
            "max_runtime_minutes",
            "max_loop_tasks",
            "max_stale_task_minutes",
            "worker_timeout_threshold",
            "claude_cli_timeout_s",
        ),
        evidence_events=("loop_stopped",),
    )),
    _h(StopHandler(
        reason="cost_budget_exceeded",
        headline="The session spend cap was reached",
        cause=(
            "Session API spend reached ${session_cost} against MAX_SESSION_COST_DOLLARS "
            "({max_session_cost_dollars}) / MAX_TASK_COST_DOLLARS "
            "({max_task_cost_dollars}); 0.0 means that particular cap is off. The guard "
            "halts the run rather than spending past a cap set deliberately."
        ),
        action=(
            "If the spend is expected, raise MAX_SESSION_COST_DOLLARS in .env and "
            "re-run. If it is not, read the per-task api_cost values in `python main.py "
            "logs` to find the expensive task. Running Claude on subscription auth "
            "(CLAUDE_AUTH_MODE=subscription) accrues no API cost at all."
        ),
        config_keys=(
            "max_session_cost_dollars",
            "max_task_cost_dollars",
            "estimated_cost_per_task_dollars",
            "cost_budget_guard_enabled",
        ),
        evidence_events=("loop_blocked_on_cost_budget",),
    )),

    # ── Liveness and failure guards ─────────────────────────────────────────
    _h(StopHandler(
        reason="stale_run",
        headline="No task completed inside the stale window",
        cause=(
            "No task has completed for {stale_minutes} minute(s), past the hard stop "
            "MAX_STALE_TASK_MINUTES ({max_stale_task_minutes}). The watchdog measures "
            "the gap from last_task_completed_at ({last_task_completed_at}) — read that "
            "timestamp before assuming a hang: a value left over from an earlier "
            "session produces this exact stop with nothing actually stuck."
        ),
        action=(
            "If last_task_completed_at predates this session's start, the state file is "
            "stale — run `python main.py reset-state` and re-run `python main.py "
            "run-loop`. If it is recent, the loop really is stuck: read the preceding "
            "events below for the node it stalled in. Only raise MAX_STALE_TASK_MINUTES "
            "if a legitimate task genuinely runs longer than {max_stale_task_minutes} "
            "min, and keep it below MAX_RUNTIME_MINUTES ({max_runtime_minutes})."
        ),
        config_keys=(
            "max_stale_task_minutes",
            "stale_run_warn_minutes",
            "max_runtime_minutes",
            "stale_run_watchdog_enabled",
        ),
        evidence_events=("loop_blocked_on_stale_run", "stale_run_warning"),
    )),
    _h(StopHandler(
        reason="consecutive_failures",
        headline="The failure circuit breaker opened",
        cause=(
            "{consecutive_failures} task(s) failed back-to-back, reaching "
            "MAX_CONSECUTIVE_FAILURES ({max_consecutive_failures}). The breaker halts "
            "the run rather than piling more tasks onto a run that is clearly going "
            "sideways; the last failing task stays queued for its retry."
        ),
        action=(
            "Read the 'error' events below — they carry the verbatim worker errors — "
            "and fix the cause they share. Raising MAX_CONSECUTIVE_FAILURES without a "
            "fix only buys more failures. `python main.py doctor --fix` repairs the "
            "queue if the failures are queue-shape problems rather than task problems."
        ),
        config_keys=(
            "max_consecutive_failures",
            "max_task_retries",
            "failure_guard_enabled",
        ),
        evidence_events=("loop_blocked_on_failures",),
    )),
    _h(StopHandler(
        reason="repeated_errors",
        headline="The same error repeated inside the error window",
        cause=(
            "The same error text appeared {match_count} time(s) within the last "
            "{repeated_error_window} failures, reaching MAX_REPEATED_ERRORS "
            "({max_repeated_errors}). A repeating identical error is an environment or "
            "task-definition problem — retrying reproduces it."
        ),
        action=(
            "Fix the error quoted in the loop_blocked_on_repeated_error event below; it "
            "is the same failure every time, so restarting without a change lands here "
            "again. If the error is a transient integration failure, widen "
            "REPEATED_ERROR_WINDOW rather than raising MAX_REPEATED_ERRORS."
        ),
        config_keys=("max_repeated_errors", "repeated_error_window"),
        evidence_events=("loop_blocked_on_repeated_error",),
    )),
    _h(StopHandler(
        reason="repeated_task",
        headline="One task was attempted too many times this session",
        cause=(
            "Task {task_id} was attempted {attempt_count} time(s) this session, reaching "
            "MAX_TASK_ATTEMPTS ({max_task_attempts}). The loop kept re-picking the same "
            "task instead of moving on, so it was halted rather than left spinning."
        ),
        action=(
            "Fix or retire that task: correct its definition, or mark it blocked so the "
            "queue moves on. `python main.py doctor` shows whether it is orphaned or "
            "duplicated and `--fix` repairs that. Attempt counts reset on restart, so "
            "re-running without a change repeats the cycle."
        ),
        config_keys=("max_task_attempts", "max_task_retries"),
        evidence_events=("loop_blocked_on_repeated_task",),
    )),
    _h(StopHandler(
        reason="worker_timeouts",
        headline="Too many worker dispatches timed out",
        cause=(
            "{timeout_count} dispatch(es) exceeded the timeout threshold this session, "
            "reaching MAX_WORKER_TIMEOUTS ({max_worker_timeouts}). A dispatch is "
            "counted as a timeout above WORKER_TIMEOUT_THRESHOLD "
            "({worker_timeout_threshold}s); the CLI itself is killed at "
            "CLAUDE_CLI_TIMEOUT_S ({claude_cli_timeout_s}s)."
        ),
        action=(
            "Check the worker CLI is actually usable before raising limits: `claude "
            "--version` and `codex --version`, and confirm the login is current. If the "
            "runs are legitimately long, raise WORKER_TIMEOUT_THRESHOLD — it must stay "
            "ABOVE CLAUDE_CLI_TIMEOUT_S and below MAX_STALE_TASK_MINUTES x 60, and "
            "`python main.py run-loop` refuses to start if that ordering is inverted."
        ),
        config_keys=(
            "max_worker_timeouts",
            "worker_timeout_threshold",
            "claude_cli_timeout_s",
            "max_stale_task_minutes",
            "worker_timeout_guard_enabled",
        ),
        evidence_events=("loop_blocked_on_worker_timeout",),
    )),
    _h(StopHandler(
        reason="worker_health_probe_failed",
        headline="The worker CLI is not usable on this machine",
        cause=(
            "The '{worker}' worker failed its health probe ({reason}) — the CLI is "
            "missing, not authenticated, or did not answer its live ping — so no task "
            "could be dispatched. Nothing was attempted; this is a machine setup "
            "problem, not a task problem."
        ),
        action=(
            "Fix the worker on this host: `claude --version` / `codex --version`, then "
            "re-authenticate the failing CLI. Alternatively set the task's "
            "preferred_worker to a healthy worker. WORKER_HEALTH_PROBE=false only "
            "removes the check — the dispatch will still fail."
        ),
        config_keys=(
            "worker_health_probe_enabled",
            "worker_health_live_ping_enabled",
            "worker_health_live_ping_timeout_s",
            "claude_auth_mode",
        ),
        evidence_events=("loop_blocked_on_worker_health", "worker_health_probe_failed"),
    )),
    _h(StopHandler(
        reason="codex_usage_limit",
        headline="Codex hit its usage limit too many times",
        cause=(
            "Codex returned a usage-limit error {usage_limit_count} time(s) this "
            "session, reaching MAX_CODEX_USAGE_LIMIT_ERRORS "
            "({max_codex_usage_limit_errors}). Further dispatches to Codex would fail "
            "the same way until the limit window resets."
        ),
        action=(
            "Wait for the Codex quota window to reset, or route the work to Claude by "
            "setting preferred_worker='claude' on the queued tasks, then re-run "
            "`python main.py run-loop`."
        ),
        config_keys=(
            "max_codex_usage_limit_errors",
            "codex_usage_limit_guard_enabled",
        ),
        evidence_events=(
            "loop_blocked_on_codex_usage_limit",
            "codex_usage_limit_detected",
        ),
    )),
    _h(StopHandler(
        reason="claude_subscription_cooldown",
        headline="Claude subscription rate limit, out of cooldown waits",
        cause=(
            "Claude returned a subscription rate-limit response and the loop had "
            "already slept through CLAUDE_SUBSCRIPTION_COOLDOWN_MAX_WAITS "
            "({claude_subscription_cooldown_max_waits}) cooldown(s) this session "
            "({cooldown_count} so far). The task was requeued, not failed — no work was "
            "lost."
        ),
        action=(
            "Wait for the subscription window to reset (resume_at is in the cooldown "
            "event below) and re-run `python main.py run-loop`; the queued task resumes "
            "where it left off. To sit through more resets in one session raise "
            "CLAUDE_SUBSCRIPTION_COOLDOWN_MAX_WAITS; to bill the API instead set "
            "CLAUDE_AUTH_MODE=api_key with ANTHROPIC_API_KEY present."
        ),
        config_keys=(
            "claude_subscription_cooldown_max_waits",
            "claude_subscription_cooldown_wait_s",
            "claude_auth_mode",
        ),
        evidence_events=(
            "loop_blocked_on_claude_subscription_cooldown",
            "claude_subscription_cooldown_detected",
        ),
    )),

    # ── Waiting on a human ──────────────────────────────────────────────────
    _h(StopHandler(
        reason="awaiting_resources",
        headline="A task needs a credential or resource the runner does not have",
        cause=(
            "Task {task_id} needs something only a human can provide (credentials: "
            "{credentials_needed}; resources: {resources_needed}), so it was marked "
            "blocked and the loop stopped waiting. Names only are ever recorded — no "
            "value is read or logged."
        ),
        action=(
            "Provide the named item(s), then signal fulfillment by creating the file "
            "the request names: `touch {fulfill_by}` (the request itself is at "
            "{review_path}). Re-run `python main.py run-loop` — blocked tasks with a "
            "fulfillment file are requeued automatically. GATE_BLOCK_SCOPE "
            "({gate_block_scope}) decides whether one blocked task stops the run or is "
            "set aside; 'proportionate' lets the loop continue with the next task."
        ),
        config_keys=("resource_gate_enabled", "gate_block_scope"),
        evidence_events=("resource_request_waiting", "resource_request_pending"),
    )),
    _h(StopHandler(
        reason="awaiting_merge_approval",
        headline="A merge needs human approval before it can land",
        cause=(
            "The merge risk classifier rated task {task_id}'s change '{risk_level}', and "
            "MERGE_APPROVAL_POLICY ({merge_approval_policy}) requires a human to approve "
            "that level before the merge runs. The branch is pushed; only the merge is "
            "held."
        ),
        action=(
            "Review the request at {review_path}, then approve with `touch {approve_by}` "
            "and re-run `python main.py run-loop`. To stop pausing at this risk level, "
            "change MERGE_APPROVAL_POLICY in .env."
        ),
        config_keys=(
            "merge_approval_policy",
            "risk_based_merge_approval_enabled",
            "merge_via_pr",
        ),
        evidence_events=("merge_approval_required",),
    )),
    _h(StopHandler(
        reason="awaiting_strategic_review",
        headline="The strategic review gate paused the run",
        cause=(
            "STRATEGIC_PAUSE_INTERVAL ({strategic_pause_interval}) task(s) have run "
            "since the last strategic review, so the gate paused the loop for a human "
            "decision about direction. Nothing failed."
        ),
        action=(
            "Read the review at {review_path}, then `touch {approve_by}` and re-run "
            "`python main.py run-loop`. Set STRATEGIC_PAUSE_INTERVAL=0 (or "
            "STRATEGIC_GATE=false) to stop pausing."
        ),
        config_keys=("strategic_gate_enabled", "strategic_pause_interval"),
        evidence_events=("strategic_gate_triggered",),
    )),

    # ── Quality gates ───────────────────────────────────────────────────────
    _h(StopHandler(
        reason="missing_acceptance_criteria",
        headline="A task had no acceptance criteria and strict mode is on",
        cause=(
            "Task {task_id} carries no concrete acceptance criteria and "
            "ACCEPTANCE_CRITERIA_STRICT_MODE is on, so it was failed before any worker "
            "ran. With GATE_BLOCK_SCOPE={gate_block_scope} this block halted the whole "
            "loop instead of only that task."
        ),
        action=(
            "Add acceptance criteria to the task's description (the issues are listed "
            "in the gate_blocked event below), or set "
            "ACCEPTANCE_CRITERIA_STRICT_MODE=false to warn instead of block. "
            "GATE_BLOCK_SCOPE=proportionate lets the loop skip the offending task and "
            "keep going."
        ),
        config_keys=(
            "acceptance_criteria_gate_enabled",
            "acceptance_criteria_strict_mode",
            "gate_block_scope",
        ),
        evidence_events=("gate_blocked",),
        gate="acceptance_criteria",
    )),
    _h(StopHandler(
        reason="definition_of_done_not_met",
        headline="The worker's output missed the definition of done",
        cause=(
            "Task {task_id} ran but its summary did not satisfy the definition-of-done "
            "gate, and DEFINITION_OF_DONE_STRICT_MODE is on, so the task was failed. "
            "With GATE_BLOCK_SCOPE={gate_block_scope} that block halted the loop."
        ),
        action=(
            "Read the issues in the gate_blocked event below — they name the missing "
            "summary fields or unmet criteria. Fix the task definition (or the worker "
            "prompt) and re-run; set DEFINITION_OF_DONE_STRICT_MODE=false to record the "
            "gap as a warning instead."
        ),
        config_keys=(
            "definition_of_done_gate_enabled",
            "definition_of_done_strict_mode",
            "gate_block_scope",
        ),
        evidence_events=("gate_blocked",),
        gate="definition_of_done",
    )),
    _h(StopHandler(
        reason="code_review_rejected",
        headline="The independent code review rejected the diff",
        cause=(
            "The independent review of task {task_id}'s actual git diff found problems "
            "(scope creep, .env edits, or a possible secret) and "
            "INDEPENDENT_CODE_REVIEW_STRICT_MODE is on, so the task was failed before "
            "any commit. Nothing was pushed."
        ),
        action=(
            "Read the issues in the gate_blocked event below and inspect the diff in "
            "{repo_path} yourself. Fix the diff or narrow the task's scope, then re-run; "
            "set INDEPENDENT_CODE_REVIEW_STRICT_MODE=false to warn instead of block."
        ),
        config_keys=(
            "independent_code_review_enabled",
            "independent_code_review_strict_mode",
            "gate_block_scope",
        ),
        evidence_events=("gate_blocked",),
        gate="independent_code_review",
    )),
    _h(StopHandler(
        reason="high_risk_review_rejected",
        headline="The high-risk Claude review rejected the change",
        cause=(
            "Task {task_id}'s change was classified high-risk and the second-opinion "
            "Claude review rejected it while HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE is on, "
            "so the task was failed before commit."
        ),
        action=(
            "Read the reviewer's issues in the gate_blocked event below and address "
            "them, then re-run. Set HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE=false to record "
            "the review as a warning instead of a block."
        ),
        config_keys=(
            "high_risk_claude_review_enabled",
            "high_risk_claude_review_strict_mode",
            "high_risk_claude_review_model",
            "gate_block_scope",
        ),
        evidence_events=("gate_blocked",),
        gate="high_risk_review",
    )),
    _h(StopHandler(
        reason="product_eval_failed",
        headline="The post-deploy product evals failed",
        cause=(
            "The product eval suite failed against {base_url} (failing: {failed}) and "
            "PRODUCT_EVAL_STRICT is on, so the loop stopped rather than shipping more "
            "work on top of a deployment that does not behave."
        ),
        action=(
            "Open {base_url} and reproduce the failing eval(s) named above; they run "
            "from PRODUCT_EVAL_CONFIG_PATH ({product_eval_config_path}). Fix the product "
            "or the eval, then re-run. Set PRODUCT_EVAL_STRICT=false to record failures "
            "without halting."
        ),
        config_keys=(
            "product_eval_enabled",
            "product_eval_strict",
            "product_eval_config_path",
            "product_eval_timeout_ms",
        ),
        evidence_events=("product_eval_failed",),
    )),

    # ── Deploy ──────────────────────────────────────────────────────────────
    _h(StopHandler(
        reason="deploy_failed",
        headline="Vercel reported a failed deployment",
        cause=(
            "The deployment reached Vercel and ended in terminal state '{state}' after "
            "{polls} poll(s) / {elapsed}s. BLOCK_ON_DEPLOY_FAILURE is on, so the loop "
            "stopped rather than stacking more tasks on a broken deployment."
        ),
        action=(
            "Open the failing build's logs in the Vercel dashboard (project "
            "{vercel_project_id}) and fix the build, then re-run `python main.py "
            "run-loop`. ROLLBACK_REVERT_POLICY ({rollback_revert_policy}) governs "
            "whether a revert is prepared automatically. Set "
            "BLOCK_ON_DEPLOY_FAILURE=false only if the loop should keep working over a "
            "broken deploy."
        ),
        config_keys=(
            "block_on_deploy_failure",
            "rollback_revert_policy",
            "vercel_project_id",
        ),
        evidence_events=("loop_blocked_on_deploy", "deploy_poll_failed"),
    )),
    _h(StopHandler(
        reason="deploy_timed_out",
        headline="Deployment polling gave up before Vercel finished",
        cause=(
            "Polling stopped after VERCEL_POLL_TIMEOUT ({vercel_poll_timeout}s, at "
            "{vercel_poll_interval}s intervals) with the deployment still in state "
            "'{state}' — a slow build and a stuck build look identical at this timeout, "
            "so the loop halted instead of guessing."
        ),
        action=(
            "Check the deployment in the Vercel dashboard (project "
            "{vercel_project_id}): if it eventually succeeded, raise "
            "VERCEL_POLL_TIMEOUT to cover the real build time and re-run. If it is "
            "genuinely stuck, fix the build first."
        ),
        config_keys=(
            "vercel_poll_timeout",
            "vercel_poll_interval",
            "block_on_deploy_failure",
            "vercel_project_id",
        ),
        evidence_events=("loop_blocked_on_deploy", "deploy_poll_timeout"),
    )),

    # ── Startup refusals ────────────────────────────────────────────────────
    _h(StopHandler(
        reason="preflight_unsafe",
        headline="Startup preflight refused to run from this state",
        cause=(
            "The startup preflight found a halting condition in {repo_path} — a dirty "
            "working tree or a branch workers must not operate on. Handing a worker a "
            "tree where intended state and in-flight edits are indistinguishable is how "
            "earlier runs ended with workers asking questions instead of shipping."
        ),
        action=(
            "Read outbox/startup_preflight.txt for the exact failing check(s). Commit or "
            "stash the pending work in {repo_path}, switch to a feature branch, then "
            "re-run `python main.py run-loop`."
        ),
        config_keys=("startup_preflight_enabled", "repo_path", "preflight_required_tables"),
        evidence_events=("preflight_report",),
    )),
    _h(StopHandler(
        reason="launch_readiness_failed",
        headline="The launch readiness scorecard failed in strict mode",
        cause=(
            "The readiness scorecard (config completeness, credentials, safety gates, "
            "operational health) scored below "
            "LAUNCH_READINESS_SCORECARD_PASS_THRESHOLD "
            "({launch_readiness_scorecard_pass_threshold}) while strict mode is on, so "
            "no task was dispatched."
        ),
        action=(
            "Read outbox/launch_readiness_scorecard.txt — it names the lowest-scoring "
            "dimension and why — and fix that, then re-run. Set "
            "LAUNCH_READINESS_SCORECARD_STRICT_MODE=false to warn instead of halt."
        ),
        config_keys=(
            "launch_readiness_scorecard_enabled",
            "launch_readiness_scorecard_strict_mode",
            "launch_readiness_scorecard_pass_threshold",
        ),
        evidence_events=("launch_readiness_failed",),
    )),

    # ── Business (foreign repo) missions ────────────────────────────────────
    _h(StopHandler(
        reason="business_not_found",
        headline="The task targets a business that does not exist",
        cause=(
            "Task {task_id} is a business-targeted mission, but no businesses row "
            "matches its business_id, so there is no repo to work in. The task was "
            "marked failed."
        ),
        action=(
            "Fix the task's business_id or create the missing business row in Supabase, "
            "then re-run. `python main.py doctor` lists seeded tasks whose parent rows "
            "have gone missing."
        ),
        config_keys=("business_execution_enabled",),
        evidence_events=("error",),
    )),
    _h(StopHandler(
        reason="business_repo_remote_mismatch",
        headline="The sandbox workspace points at the wrong repository",
        cause=(
            "The workspace's git origin does not match the business's configured repo "
            "(expected '{expected}', found '{actual}' — {reason}). Every commit, push "
            "and deploy after this point would have gone to the wrong repository, so "
            "the run was stopped before any of them."
        ),
        action=(
            "Delete the stale workspace directory for this business so it is re-cloned "
            "from the right origin, or correct repo_full_name in that business's sandbox "
            "settings. Then re-run `python main.py run-loop`."
        ),
        config_keys=("business_execution_enabled",),
        evidence_events=("business_repo_remote_mismatch",),
    )),
    _h(StopHandler(
        reason="business_repo_forbidden",
        headline="A business sandbox resolves to the bucks-ai repo itself",
        cause=(
            "The business's configured repo_full_name resolves to the bucks-ai "
            "repository. A customer mission is never allowed to write to the runner's "
            "own source tree, so the task was failed and the run stopped."
        ),
        action=(
            "Change that business's sandbox repo_full_name (Settings -> sandbox config) "
            "to the customer's own repository, then re-run `python main.py run-loop`."
        ),
        config_keys=("business_execution_enabled", "repo_path"),
        evidence_events=("error",),
    )),

    # ── Fallback ────────────────────────────────────────────────────────────
    _h(StopHandler(
        reason=UNSPECIFIED_STOP,
        headline="The loop stopped without recording a stop reason",
        cause=(
            "The run reached the stop path with state.status='stopped' but no "
            "stop_reason set. Some node marked the loop stopped without saying why — "
            "that is a bug in the node, not a condition of the run."
        ),
        action=(
            "Read the preceding events below to find the last node that ran "
            "(last_completed_step={last_completed_step}), then make that node set a "
            "stop_reason with a matching handler in `tools/stop_diagnostics.py` — "
            "`python main.py logs` shows the same trail in full."
        ),
        config_keys=("max_loop_tasks", "max_runtime_minutes"),
    )),
])


# ---------------------------------------------------------------------------
# Classification and lookup
# ---------------------------------------------------------------------------

def classify_stop(stop_reason: Optional[str]) -> str:
    """EXPECTED when the run ended as configured, ANOMALOUS when it broke.

    This is the field m4c-06's watchdog reads to decide whether to auto-restart,
    so an unknown reason is deliberately ANOMALOUS: a stop nobody has classified
    is exactly the kind that should wake a human.
    """
    if stop_reason in EXPECTED_STOP_REASONS:
        return EXPECTED
    return ANOMALOUS


def get_handler(stop_reason: Optional[str]) -> Optional[StopHandler]:
    if not stop_reason:
        return STOP_HANDLERS.get(UNSPECIFIED_STOP)
    return STOP_HANDLERS.get(stop_reason)


def unhandled_stop_reasons(reasons) -> list[str]:
    """Return the reasons with no registered handler, sorted.

    Used by the test that scans the runner source for stop reasons; a non-empty
    result is a test failure, which is what makes diagnostics non-optional for
    any new stop reason.
    """
    return sorted({r for r in reasons if r not in STOP_HANDLERS})


# ---------------------------------------------------------------------------
# Evidence collection
# ---------------------------------------------------------------------------

def collect_recent_events(events: list[dict], limit: int = RECENT_EVENT_COUNT) -> list[dict]:
    """Return the last ``limit`` events that precede the stop, oldest first."""
    useful = [e for e in (events or []) if e.get("event_type") not in _REPORTING_EVENTS]
    return useful[-limit:] if limit else useful


def collect_evidence(events: list[dict], handler: Optional[StopHandler]) -> dict:
    """Pull the observed numbers out of the stop's own log events.

    Scans newest-first for the handler's evidence events and returns the payload
    of the first match. When the handler names a ``gate``, generic events (every
    quality gate logs ``gate_blocked``) must also match that gate, so one gate's
    numbers are never reported under another gate's stop.
    """
    if not handler or not handler.evidence_events:
        return {}
    wanted = handler.evidence_events
    for event in reversed(events or []):
        if event.get("event_type") not in wanted:
            continue
        payload = event.get("payload") or {}
        if handler.gate and payload.get("gate") not in (None, handler.gate):
            continue
        evidence = {k: v for k, v in payload.items()}
        if event.get("task_id") and "task_id" not in evidence:
            evidence["task_id"] = event["task_id"]
        return evidence
    return {}


def collect_config_values(config_report: dict, handler: Optional[StopHandler]) -> dict:
    """Return ``{config_key: value}`` for the config that produced this stop."""
    if not handler:
        return {}
    values: dict = {}
    for key in handler.config_keys:
        if is_secret_key(key):
            values[key] = _REDACTED
        else:
            values[key] = (config_report or {}).get(key)
    return values


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def consistency_warnings(
    reason: str,
    session_state: dict,
    config_values: dict,
) -> list[str]:
    """Flag stops whose own numbers do not support them.

    A stop reason inherited from a previous session reproduces a real stop
    exactly — ``run-loop`` clears state on start (``start_fresh_session``),
    ``run-once`` and ``dry-run`` do not. Without this check the report narrates
    the budget stop it was told about ("completed 0 task loop(s), reaching
    MAX_LOOP_TASKS (2)") in the same confident voice as a true one, which is the
    misdiagnosis this module exists to end — so where the arithmetic can be
    checked, it is.
    """
    warnings: list[str] = []
    stale_state_fix = (
        "A stop_reason left in .runtime/state.local.json by a previous session "
        "reproduces this exactly: `python main.py run-loop` clears it on start, "
        "`run-once` and `dry-run` do not. Run `python main.py reset-state`, then "
        "re-read this report."
    )

    loop_count = session_state.get("loop_count")
    max_loop = config_values.get("max_loop_tasks")
    if (
        reason == "max_loop_tasks"
        and isinstance(loop_count, int) and isinstance(max_loop, int)
        and max_loop > 0 and loop_count < max_loop
    ):
        warnings.append(
            f"The numbers do not support this stop: {loop_count} task loop(s) ran "
            f"but MAX_LOOP_TASKS is {max_loop}. {stale_state_fix}"
        )

    max_runtime = config_values.get("max_runtime_minutes")
    elapsed = _elapsed_minutes(session_state.get("started_at"))
    if (
        reason == "max_runtime"
        and elapsed is not None
        and isinstance(max_runtime, (int, float)) and max_runtime > 0
        and elapsed < max_runtime
    ):
        warnings.append(
            f"The numbers do not support this stop: the session has run "
            f"{elapsed:.1f} min but MAX_RUNTIME_MINUTES is {max_runtime}. "
            f"{stale_state_fix}"
        )

    return warnings


def _elapsed_minutes(started_at: Optional[str]) -> Optional[float]:
    if not started_at:
        return None
    try:
        return (datetime.utcnow() - datetime.fromisoformat(started_at)).total_seconds() / 60
    except (ValueError, TypeError):
        return None


class _SafeContext(dict):
    """format_map source that renders unknown placeholders as ``unknown``."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - trivial
        return "unknown"


def _render(template: str, context: dict) -> str:
    try:
        return template.format_map(_SafeContext(context))
    except (ValueError, IndexError):
        # A malformed template must never cost the founder the report.
        return template


def _fmt_value(value: Any, max_len: int = 160) -> str:
    if value is None:
        return "unset"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        if not value:
            return "none"
        return _truncate(", ".join(_fmt_value(v, 60) for v in value), max_len)
    if isinstance(value, dict):
        if not value:
            return "none"
        pairs = ", ".join(f"{k}={_fmt_value(v, 40)}" for k, v in list(value.items())[:6])
        return _truncate(pairs, max_len)
    return _truncate(str(value), max_len)


def _truncate(text: str, max_len: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= max_len else text[: max(0, max_len - 3)] + "..."


def _short_time(timestamp: Optional[str]) -> str:
    if not timestamp:
        return "?"
    try:
        return datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
    except (ValueError, TypeError):
        return str(timestamp)[:19]


def _event_one_liner(event: dict, max_len: int = 200) -> str:
    payload = event.get("payload") or {}
    scalars = {
        k: v for k, v in payload.items()
        if not isinstance(v, (dict,)) and k not in ("message",)
    }
    bits = [f"{k}: {_fmt_value(v, 60)}" for k, v in list(scalars.items())[:5]]
    detail = "  ".join(bits)
    if payload.get("message"):
        detail = f"{detail}  {payload['message']}" if detail else str(payload["message"])
    return _truncate(detail, max_len)


# ---------------------------------------------------------------------------
# Diagnostics builder
# ---------------------------------------------------------------------------

def build_stop_diagnostics(
    *,
    stop_reason: Optional[str],
    session_state: dict,
    config_report: dict,
    events: Optional[list[dict]] = None,
    task: Optional[dict] = None,
) -> dict:
    """Build the structured record behind both the outbox file and Slack message.

    Args:
        stop_reason    — the loop's ``state.stop_reason`` (None is reported as
                         ``unspecified`` rather than silently skipped).
        session_state  — ``RunnerState.model_dump()`` (or a subset).
        config_report  — ``cfg.report()``.
        events         — flight-recorder events, oldest first; read from
                         ``logs/runs.jsonl`` when omitted.
        task           — the triggering task dict; falls back to
                         ``session_state["current_task"]``.

    Returns a dict with ``reason``, ``classification``, ``handler_found``,
    ``cause``, ``action``, ``task``, ``config_values``, ``evidence``,
    ``recent_events``, ``report`` and ``slack_message``.
    """
    session_state = session_state or {}
    config_report = config_report or {}
    reason = stop_reason or UNSPECIFIED_STOP
    handler = get_handler(reason)
    classification = classify_stop(stop_reason)

    if events is None:
        events = read_logs(tail=_EVENT_SCAN_DEPTH)

    evidence = collect_evidence(events, handler)
    config_values = collect_config_values(config_report, handler)
    recent_events = collect_recent_events(events)

    task = task or session_state.get("current_task") or {}
    task_view = {
        "id": task.get("id") or session_state.get("current_task_id"),
        "title": task.get("title"),
        "status": task.get("status"),
        "type": task.get("type"),
        "branch": task.get("branch") or session_state.get("current_branch"),
        "worker": session_state.get("current_worker") or task.get("preferred_worker"),
        "error": task.get("error"),
    }

    # Guards fire with the threshold in their payload, so evidence and config
    # can carry the same key. Config wins, and the duplicate is dropped from the
    # observed list: one name showing two numbers in the report that exists to
    # print observed-vs-configured would be its own small misdiagnosis.
    observed = {
        k: v for k, v in evidence.items()
        if k not in config_values and k not in _OBSERVED_NOISE_KEYS
    }

    context = _SafeContext({
        **{k: _fmt_value(v) for k, v in evidence.items()},
        **{k: _fmt_value(v) for k, v in config_values.items()},
        "task_id": task_view["id"] or evidence.get("task_id") or "unknown",
        "loop_count": session_state.get("loop_count", "unknown"),
        "consecutive_failures": session_state.get("consecutive_failures", "unknown"),
        "session_cost": _fmt_value(session_state.get("session_cost")),
        "last_completed_step": session_state.get("last_completed_step") or "unknown",
        "last_task_completed_at": (
            evidence.get("last_task_completed_at")
            or session_state.get("last_task_completed_at")
            or "never (no task completed this session)"
        ),
        "cooldown_count": session_state.get("claude_subscription_cooldown_count", "unknown"),
    })

    cause = _render(handler.cause, context) if handler else _no_handler_cause(reason)
    action = _render(handler.action, context) if handler else _no_handler_action(reason)

    diagnostics = {
        "reason": reason,
        "classification": classification,
        "handler_found": handler is not None,
        "headline": handler.headline if handler else "No diagnostics handler for this stop",
        "cause": cause,
        "action": action,
        "warnings": consistency_warnings(reason, session_state, config_values),
        "task": task_view,
        "config_values": config_values,
        "evidence": observed,
        "recent_events": recent_events,
        "session": {
            "loop_count": session_state.get("loop_count"),
            "started_at": session_state.get("started_at"),
            "session_cost": session_state.get("session_cost"),
            "consecutive_failures": session_state.get("consecutive_failures"),
            "worker_timeout_count": session_state.get("worker_timeout_count"),
            "last_completed_step": session_state.get("last_completed_step"),
            "last_task_completed_at": session_state.get("last_task_completed_at"),
        },
    }
    diagnostics["report"] = format_stop_report(diagnostics)
    diagnostics["slack_message"] = format_slack_message(diagnostics)
    return diagnostics


def _no_handler_cause(reason: str) -> str:
    return (
        f"The loop stopped with reason '{reason}', which has no handler in "
        "tools/stop_diagnostics.py — so the runner cannot say what caused it. The "
        "missing handler is itself the defect: every stop reason is required to "
        "carry a cause and a fix."
    )


def _no_handler_action(reason: str) -> str:
    return (
        f"Add a StopHandler for '{reason}' to STOP_HANDLERS in "
        "tools/stop_diagnostics.py (cause, action, config_keys, evidence_events) and "
        "classify it in EXPECTED_STOP_REASONS if it is a normal finish. "
        "tests/test_stop_diagnostics.py fails until you do. Meanwhile, read the "
        "preceding events below for what actually happened."
    )


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_WIDTH = 72
_RULE = "=" * _WIDTH
_THIN = "-" * _WIDTH

_CLASSIFICATION_GLOSS = {
    EXPECTED: "the run ended the way it was configured to — nothing to fix",
    ANOMALOUS: "the run did not finish on its own terms — read this before restarting",
}


def format_stop_report(diagnostics: dict) -> str:
    """Render the single structured record written to outbox/loop_stop_report.txt."""
    reason = diagnostics.get("reason", UNSPECIFIED_STOP)
    classification = diagnostics.get("classification", ANOMALOUS)
    task = diagnostics.get("task") or {}
    session = diagnostics.get("session") or {}
    config_values = diagnostics.get("config_values") or {}
    evidence = diagnostics.get("evidence") or {}

    lines = [
        _RULE,
        f"LOOP STOP REPORT — {classification}",
        _RULE,
        "",
        f"  Stop reason  : {reason}",
        f"  Headline     : {diagnostics.get('headline', '')}",
        f"  Classified   : {classification} ({_CLASSIFICATION_GLOSS.get(classification, '')})",
        f"  Written at   : {datetime.utcnow().isoformat()}",
        f"  Loop count   : {_fmt_value(session.get('loop_count'))}",
        f"  Started at   : {_fmt_value(session.get('started_at'))}",
        f"  Last step    : {_fmt_value(session.get('last_completed_step'))}",
        "",
        "TRIGGERING TASK",
        _THIN,
        f"  ID     : {_fmt_value(task.get('id'))}",
        f"  Title  : {_fmt_value(task.get('title'))}",
        f"  Status : {_fmt_value(task.get('status'))}",
        f"  Type   : {_fmt_value(task.get('type'))}",
        f"  Branch : {_fmt_value(task.get('branch'))}",
        f"  Worker : {_fmt_value(task.get('worker'))}",
        f"  Error  : {_fmt_value(task.get('error'), 300)}",
    ]

    for warning in diagnostics.get("warnings") or []:
        lines.extend(["", "SUSPECT — READ THIS FIRST", _THIN])
        lines.extend(_wrap(warning, indent="  "))

    lines.extend(["", "CAUSE", _THIN])
    lines.extend(_wrap(diagnostics.get("cause", ""), indent="  "))
    lines.extend(["", "RECOMMENDED ACTION", _THIN])
    lines.extend(_wrap(diagnostics.get("action", ""), indent="  "))

    lines.extend(["", "CONFIG THAT PRODUCED THIS STOP", _THIN])
    if config_values:
        width = max(len(env_name_for(k)) for k in config_values)
        for key, value in config_values.items():
            lines.append(f"  {env_name_for(key):<{width}} = {_fmt_value(value)}   ({key})")
    else:
        lines.append("  (no config threshold governs this stop)")

    if evidence:
        lines.extend(["", "OBSERVED AT THE STOP", _THIN])
        width = max(len(k) for k in evidence)
        for key, value in list(evidence.items())[:12]:
            lines.append(f"  {key:<{width}} = {_fmt_value(value, 220)}")

    recent = diagnostics.get("recent_events") or []
    lines.extend(["", f"PRECEDING {len(recent)} EVENT(S)", _THIN])
    if recent:
        for i, event in enumerate(recent, 1):
            head = f"  {i}. {_short_time(event.get('timestamp'))}  {event.get('event_type', '?')}"
            if event.get("task_id"):
                head += f"  task={event['task_id']}"
            lines.append(head)
            detail = _event_one_liner(event)
            if detail:
                lines.append(f"       {detail}")
    else:
        lines.append("  (no events recorded before this stop)")

    lines.extend(["", _RULE, ""])
    return "\n".join(lines)


def format_slack_message(diagnostics: dict) -> str:
    """One Slack message: classification first, then cause, action, numbers."""
    reason = diagnostics.get("reason", UNSPECIFIED_STOP)
    classification = diagnostics.get("classification", ANOMALOUS)
    marker = ":checkered_flag:" if classification == EXPECTED else ":rotating_light:"
    task = diagnostics.get("task") or {}
    config_values = diagnostics.get("config_values") or {}
    evidence = diagnostics.get("evidence") or {}

    lines = [
        f"{marker} *{classification}* — loop stopped: `{reason}`",
        f"_{diagnostics.get('headline', '')}_",
    ]

    for warning in diagnostics.get("warnings") or []:
        lines.append(f":warning: *SUSPECT*: {warning}")

    task_id = task.get("id")
    if task_id:
        bits = [f"*Task*: `{task_id}`"]
        if task.get("status"):
            bits.append(f"({task['status']})")
        if task.get("title"):
            bits.append(_truncate(str(task["title"]), 80))
        lines.append(" ".join(bits))

    lines.append(f"*CAUSE*: {diagnostics.get('cause', '')}")
    lines.append(f"*RECOMMENDED ACTION*: {diagnostics.get('action', '')}")

    if config_values:
        rendered = "  ·  ".join(
            f"{env_name_for(k)}={_fmt_value(v, 60)}" for k, v in config_values.items()
        )
        lines.append(f"*Config*: {rendered}")

    if evidence:
        rendered = "  ·  ".join(
            f"{k}={_fmt_value(v, 60)}" for k, v in list(evidence.items())[:6]
        )
        lines.append(f"*Observed*: {rendered}")

    recent = diagnostics.get("recent_events") or []
    if recent:
        trail = " → ".join(e.get("event_type", "?") for e in recent)
        lines.append(f"*Last {len(recent)} events*: {trail}")

    lines.append(f"*Full report*: runner/langgraph/outbox/{STOP_REPORT_FILENAME}")
    return "\n".join(lines)


def _wrap(text: str, indent: str = "  ", width: int = _WIDTH) -> list[str]:
    """Wrap a sentence to the report width without pulling in textwrap's
    paragraph handling (the templates are single paragraphs)."""
    words = str(text).split()
    if not words:
        return [f"{indent}(none)"]
    lines: list[str] = []
    current = indent
    for word in words:
        candidate = word if current.strip() == "" else f"{current} {word}"
        if len(candidate) > width and current.strip():
            lines.append(current)
            current = f"{indent}{word}"
        else:
            current = candidate if current.strip() else f"{indent}{word}"
    lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def report_loop_stop(
    *,
    stop_reason: Optional[str],
    session_state: dict,
    config_report: dict,
    outbox_dir,
    events: Optional[list[dict]] = None,
    task: Optional[dict] = None,
) -> dict:
    """Write the one stop record and fire the one Slack message.

    The Slack fan-out rides the flight recorder: ``log_event`` posts
    ``loop_stop_report`` when it is in ``SLACK_NOTIFY_EVENTS`` (it is, by
    default), and ``slack_tools`` renders ``payload["message"]`` verbatim — so
    the file and the phone carry the same diagnosis.

    Never raises: a failure to write the report must not change how the run
    ended. A write failure is recorded in the returned dict.
    """
    diagnostics = build_stop_diagnostics(
        stop_reason=stop_reason,
        session_state=session_state,
        config_report=config_report,
        events=events,
        task=task,
    )

    report_path = Path(outbox_dir) / STOP_REPORT_FILENAME
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(diagnostics["report"])
        diagnostics["report_path"] = str(report_path)
    except OSError as e:
        diagnostics["report_path"] = None
        diagnostics["write_error"] = str(e)

    log_event(STOP_REPORT_EVENT, {
        "reason": diagnostics["reason"],
        "classification": diagnostics["classification"],
        "handler_found": diagnostics["handler_found"],
        "headline": diagnostics["headline"],
        "cause": diagnostics["cause"],
        "warnings": diagnostics["warnings"],
        "recommended_action": diagnostics["action"],
        "task": diagnostics["task"],
        "config_values": diagnostics["config_values"],
        "observed": diagnostics["evidence"],
        "preceding_events": [
            {
                "event_type": e.get("event_type"),
                "timestamp": e.get("timestamp"),
                "task_id": e.get("task_id"),
            }
            for e in diagnostics["recent_events"]
        ],
        "report_path": diagnostics.get("report_path"),
        "message": diagnostics["slack_message"],
    }, task_id=diagnostics["task"].get("id"))

    return diagnostics
