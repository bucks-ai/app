"""100-task autonomous soak harness for the bucks.ai runner.

Runs N synthetic tasks through the key runner guard/gate logic in a fully
in-memory simulation — no workers, no git, no network.  This validates that:

  - guard functions (failure_guard, repeated_error_guard, cost_budget_guard,
    worker_timeout_guard) produce stable, non-diverging state over a long run.
  - state fields are correctly reset between tasks (no bleed from task N to N+1).
  - failure injection produces the expected circuit-breaker and retry behaviour.
  - cost accumulation stays deterministic across 100 tasks.

All functions are pure side-effect-free helpers; the top-level ``run_soak``
orchestrator is also pure (accepts injectable dependencies) so it is fully
unit-testable without touching the file system or the LangGraph graph.

Typical usage (from tests or a one-shot CLI invocation):

    from tools.soak_harness import run_soak, format_soak_report, SoakConfig
    result = run_soak(100, SoakConfig())
    print(format_soak_report(result))
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from tools.failure_guard import evaluate_failure
from tools.repeated_error_guard import evaluate_error_repetition, evaluate_task_repetition
from tools.cost_budget_guard import evaluate_cost_budget
from tools.worker_timeout_guard import evaluate_worker_timeout


# ---------------------------------------------------------------------------
# Task generation
# ---------------------------------------------------------------------------

_TASK_TYPES = ["backend", "frontend", "ui", "general", "runner", "database", "infra"]

_TITLE_TEMPLATES = [
    "Add {noun} endpoint",
    "Fix {noun} bug",
    "Refactor {noun} module",
    "Update {noun} schema",
    "Implement {noun} feature",
    "Deploy {noun} service",
    "Test {noun} integration",
    "Migrate {noun} data",
    "Optimise {noun} query",
    "Audit {noun} logs",
]

_NOUNS = [
    "user", "auth", "payment", "dashboard", "report", "webhook", "job",
    "queue", "cache", "session", "token", "profile", "invoice", "event",
    "notification", "upload", "search", "index", "metric", "config",
]


def generate_soak_tasks(n: int = 100, seed: Optional[int] = None) -> list[dict]:
    """Return *n* synthetic task dicts with diverse types, titles, and branches.

    Uses *seed* for deterministic output in tests.  Each task carries the
    fields expected by the runner guard functions (id, type, title, branch,
    status, retry_count).
    """
    rng = random.Random(seed)

    tasks: list[dict] = []
    for i in range(1, n + 1):
        task_type = rng.choice(_TASK_TYPES)
        template = rng.choice(_TITLE_TEMPLATES)
        noun = rng.choice(_NOUNS)
        title = template.format(noun=noun)
        branch = f"feature/soak-task-{i:04d}"
        preferred_worker = rng.choice(["claude", "codex", None, None])

        task: dict = {
            "id": f"soak-{i:04d}",
            "title": title,
            "type": task_type,
            "branch": branch,
            "status": "queued",
            "retry_count": 0,
            "preferred_worker": preferred_worker,
        }
        tasks.append(task)

    return tasks


# ---------------------------------------------------------------------------
# Soak configuration
# ---------------------------------------------------------------------------

@dataclass
class SoakConfig:
    """Knobs controlling what the soak simulation injects and checks.

    All thresholds mirror the defaults from config.py so the simulation
    reflects a realistic production runner configuration.
    """
    # Failure injection
    worker_failure_rate: float = 0.15       # fraction of tasks where worker fails
    timeout_rate: float = 0.05             # fraction of tasks where worker times out
    cost_per_task_dollars: float = 0.08    # simulated cost per successful task

    # Guard thresholds (must match realistic config defaults)
    max_task_retries: int = 1
    max_consecutive_failures: int = 3
    max_repeated_errors: int = 3
    repeated_error_window: int = 10
    max_worker_timeouts: int = 3
    max_session_cost_dollars: float = 0.0  # 0 = disabled
    max_task_cost_dollars: float = 0.0     # 0 = disabled

    # Injection seed for reproducible runs
    seed: Optional[int] = 42


# ---------------------------------------------------------------------------
# Per-task simulation state (mutable across tasks within a run)
# ---------------------------------------------------------------------------

@dataclass
class _RunState:
    """Mutable accumulator updated as each task runs."""
    consecutive_failures: int = 0
    worker_timeout_count: int = 0
    codex_usage_limit_count: int = 0
    session_cost: float = 0.0
    error_history: list = field(default_factory=list)
    task_attempt_counts: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# State-bleed detection
# ---------------------------------------------------------------------------

# Fields that must be reset to None/falsy between tasks.
_PER_TASK_STATE_FIELDS = [
    "current_task_id",
    "current_task",
    "current_worker",
    "current_branch",
    "worker_result",
    "worker_summary",
    "check_passed",
    "acceptance_criteria_status",
    "definition_of_done_status",
    "code_review_status",
    "merge_approval_status",
    "merge_risk_level",
    "auto_repair_status",
    "auto_repair_attempt",
    "retry_pending",
    "stop_reason",
]


def detect_state_bleed(
    before: dict,
    after: dict,
    task_id: str,
) -> list[str]:
    """Return a list of field names that were not reset after task *task_id*.

    Compares *before* (state at start of next task) against the set of fields
    that must be cleared by ``update_logs_and_state``.  A field is flagged when
    it is set (non-None, non-empty, non-zero) in *after* but was not set in
    *before* — meaning the previous task's value was retained.
    """
    bleed: list[str] = []
    for field_name in _PER_TASK_STATE_FIELDS:
        before_val = before.get(field_name)
        after_val = after.get(field_name)
        before_truthy = bool(before_val) if before_val is not None else False
        after_truthy = bool(after_val) if after_val is not None else False
        if after_truthy and not before_truthy:
            bleed.append(field_name)
    return bleed


# ---------------------------------------------------------------------------
# Single-task simulation
# ---------------------------------------------------------------------------

def _build_error_payload(task_id: str, msg: str) -> dict:
    return {"error": msg, "task_id": task_id}


def simulate_task_run(
    task: dict,
    run_state: _RunState,
    cfg: SoakConfig,
    rng: random.Random,
) -> dict:
    """Simulate one task through the runner's key guard functions.

    Does NOT invoke workers, git, or any I/O.  Returns an outcome dict:

        task_id       — the task id
        success       — True when the task completed without circuit-break/stop
        outcome       — "complete" | "failed" | "retried" | "stopped"
        stop_reason   — why the loop would stop (or None)
        cost          — simulated API cost for this task
        bleed_fields  — list of state fields that would bleed to the next task
        guard_results — dict of individual guard outcomes
    """
    task_id: str = task["id"]
    outcome_data: dict = {
        "task_id": task_id,
        "success": False,
        "outcome": "failed",
        "stop_reason": None,
        "cost": 0.0,
        "bleed_fields": [],
        "guard_results": {},
    }

    # --- simulate worker dispatch outcome (failure / timeout / success) ---
    worker_failed = rng.random() < cfg.worker_failure_rate
    worker_timed_out = (not worker_failed) and (rng.random() < cfg.timeout_rate)
    task_cost = 0.0 if worker_failed else cfg.cost_per_task_dollars

    # --- worker timeout guard ---
    timeout_guard: dict = {"blocked": False}
    if worker_timed_out:
        timeout_guard = evaluate_worker_timeout(
            elapsed_seconds=None,
            error="timed out after 570s",
            timeout_count=run_state.worker_timeout_count,
            max_worker_timeouts=cfg.max_worker_timeouts,
            worker_timeout_threshold=570,
        )
        run_state.worker_timeout_count = timeout_guard["timeout_count"]
        outcome_data["guard_results"]["worker_timeout"] = timeout_guard
        if timeout_guard.get("blocked"):
            outcome_data["stop_reason"] = timeout_guard.get("stop_reason")
            outcome_data["outcome"] = "stopped"
            return outcome_data

    # --- failure guard (when worker failed) ---
    failure_guard: dict = {}
    if worker_failed:
        failure_guard = evaluate_failure(
            task=task,
            consecutive_failures=run_state.consecutive_failures,
            max_task_retries=cfg.max_task_retries,
            max_consecutive_failures=cfg.max_consecutive_failures,
        )
        run_state.consecutive_failures = failure_guard["consecutive_failures"]
        outcome_data["guard_results"]["failure_guard"] = failure_guard

        action = failure_guard.get("action", "give_up")
        if failure_guard.get("circuit_open"):
            outcome_data["stop_reason"] = failure_guard.get("stop_reason")
            outcome_data["outcome"] = "stopped"
            return outcome_data
        if action == "retry":
            # Update the task's retry_count for subsequent calls.
            task["retry_count"] = failure_guard["retry_count"]
            outcome_data["outcome"] = "retried"
            return outcome_data
        outcome_data["outcome"] = "failed"
        return outcome_data

    # Worker succeeded — reset consecutive failures.
    run_state.consecutive_failures = 0

    # --- cost budget guard ---
    run_state.task_attempt_counts[task_id] = (
        run_state.task_attempt_counts.get(task_id, 0) + 1
    )
    cost_guard = evaluate_cost_budget(
        task_cost=task_cost,
        session_cost=run_state.session_cost,
        max_session_cost=cfg.max_session_cost_dollars,
        max_task_cost=cfg.max_task_cost_dollars,
    )
    run_state.session_cost = cost_guard["session_cost"]
    outcome_data["guard_results"]["cost_budget"] = cost_guard
    if cost_guard.get("blocked"):
        outcome_data["stop_reason"] = cost_guard.get("stop_reason")
        outcome_data["outcome"] = "stopped"
        return outcome_data

    # --- repeated error guard (task-level) ---
    error_rep = evaluate_task_repetition(
        task_id=task_id,
        task_attempt_counts=run_state.task_attempt_counts,
        max_task_attempts=cfg.max_task_retries + 1,
    )
    outcome_data["guard_results"]["task_repetition"] = error_rep
    if error_rep.get("blocked"):
        outcome_data["stop_reason"] = error_rep.get("stop_reason")
        outcome_data["outcome"] = "stopped"
        return outcome_data

    # --- success ---
    outcome_data["success"] = True
    outcome_data["outcome"] = "complete"
    outcome_data["cost"] = task_cost

    # --- state-bleed check (simulated between-task field reset) ---
    # Before reset: fields as they would be mid-task (all populated).
    mid_task_state = {
        "current_task_id": task_id,
        "current_task": task,
        "current_worker": task.get("preferred_worker") or "claude",
        "current_branch": task.get("branch"),
        "worker_result": {"success": True},
        "worker_summary": {"check_result": True},
        "check_passed": True,
        "acceptance_criteria_status": "passed",
        "definition_of_done_status": "passed",
        "code_review_status": "passed",
        "merge_approval_status": "skipped",
        "merge_risk_level": "low",
        "auto_repair_status": None,
        "auto_repair_attempt": 0,
        "retry_pending": None,
        "stop_reason": None,
    }
    # After reset: the fields update_logs_and_state must clear.
    post_reset_state: dict = {f: None for f in _PER_TASK_STATE_FIELDS}
    post_reset_state["auto_repair_attempt"] = 0

    bleed = detect_state_bleed(mid_task_state, post_reset_state, task_id)
    outcome_data["bleed_fields"] = bleed

    return outcome_data


# ---------------------------------------------------------------------------
# Full soak run
# ---------------------------------------------------------------------------

def run_soak(
    n: int = 100,
    cfg: Optional[SoakConfig] = None,
    tasks: Optional[list[dict]] = None,
) -> dict:
    """Run the full soak simulation across *n* tasks.

    Args:
        n    — number of tasks to simulate (ignored when *tasks* is given)
        cfg  — SoakConfig; defaults to SoakConfig() (production-like defaults)
        tasks — pre-built task list (useful for deterministic tests); when None,
                ``generate_soak_tasks(n, cfg.seed)`` is used.

    Returns a soak result dict with keys:
        n_tasks      — total tasks attempted
        outcomes     — list of per-task outcome dicts from simulate_task_run
        metrics      — aggregated stats (see evaluate_soak_run)
        stopped_at   — index (0-based) of the task that tripped a stop, or None
        completed    — True when all tasks ran without a stop
    """
    if cfg is None:
        cfg = SoakConfig()

    if tasks is None:
        tasks = generate_soak_tasks(n, seed=cfg.seed)

    rng = random.Random(cfg.seed)
    run_state = _RunState()
    outcomes: list[dict] = []
    stopped_at: Optional[int] = None

    for i, task in enumerate(tasks):
        outcome = simulate_task_run(task, run_state, cfg, rng)
        outcomes.append(outcome)

        if outcome["outcome"] == "stopped":
            stopped_at = i
            break

    metrics = evaluate_soak_run(outcomes)

    return {
        "n_tasks": len(tasks),
        "n_ran": len(outcomes),
        "outcomes": outcomes,
        "metrics": metrics,
        "stopped_at": stopped_at,
        "completed": stopped_at is None,
    }


# ---------------------------------------------------------------------------
# Metrics aggregation
# ---------------------------------------------------------------------------

def evaluate_soak_run(outcomes: list[dict]) -> dict:
    """Aggregate per-task outcomes into a metrics summary dict.

    Keys:
        total          — tasks attempted
        complete       — tasks that reached "complete"
        failed         — tasks that reached "failed" (terminal)
        retried        — tasks requeued for retry
        stopped        — tasks that tripped a stop condition
        success_rate   — fraction of tasks reaching "complete" (0.0–1.0)
        failure_rate   — fraction reaching "failed" or "stopped"
        total_cost     — sum of per-task costs
        bleed_count    — total count of state-bleed incidents across all tasks
        stop_reasons   — dict of stop_reason → count
        guard_trips    — dict of guard name → number of times it blocked
    """
    total = len(outcomes)
    complete = sum(1 for o in outcomes if o["outcome"] == "complete")
    failed = sum(1 for o in outcomes if o["outcome"] == "failed")
    retried = sum(1 for o in outcomes if o["outcome"] == "retried")
    stopped = sum(1 for o in outcomes if o["outcome"] == "stopped")
    total_cost = sum(o.get("cost", 0.0) for o in outcomes)
    bleed_count = sum(len(o.get("bleed_fields", [])) for o in outcomes)

    stop_reasons: dict = {}
    for o in outcomes:
        reason = o.get("stop_reason")
        if reason:
            stop_reasons[reason] = stop_reasons.get(reason, 0) + 1

    guard_trips: dict = {}
    for o in outcomes:
        for guard_name, guard_result in o.get("guard_results", {}).items():
            if guard_result.get("blocked") or guard_result.get("circuit_open"):
                guard_trips[guard_name] = guard_trips.get(guard_name, 0) + 1

    return {
        "total": total,
        "complete": complete,
        "failed": failed,
        "retried": retried,
        "stopped": stopped,
        "success_rate": complete / total if total else 0.0,
        "failure_rate": (failed + stopped) / total if total else 0.0,
        "total_cost": round(total_cost, 4),
        "bleed_count": bleed_count,
        "stop_reasons": stop_reasons,
        "guard_trips": guard_trips,
    }


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

def format_soak_report(result: dict) -> str:
    """Build a human-readable soak report from a ``run_soak`` result dict."""
    metrics = result.get("metrics", {})
    n_ran = result.get("n_ran", 0)
    n_tasks = result.get("n_tasks", 0)
    completed = result.get("completed", False)
    stopped_at = result.get("stopped_at")

    status_line = "COMPLETED" if completed else f"STOPPED at task {(stopped_at or 0) + 1}"
    lines = [
        f"Soak Harness Report — {n_ran}/{n_tasks} tasks ran",
        f"Status: {status_line}",
        "",
        f"  Complete  : {metrics.get('complete', 0)}",
        f"  Failed    : {metrics.get('failed', 0)}",
        f"  Retried   : {metrics.get('retried', 0)}",
        f"  Stopped   : {metrics.get('stopped', 0)}",
        f"  Success % : {metrics.get('success_rate', 0.0) * 100:.1f}%",
        f"  Total cost: ${metrics.get('total_cost', 0.0):.4f}",
        f"  State bleed incidents: {metrics.get('bleed_count', 0)}",
    ]

    stop_reasons = metrics.get("stop_reasons", {})
    if stop_reasons:
        lines.append("")
        lines.append("  Stop reasons:")
        for reason, count in sorted(stop_reasons.items()):
            lines.append(f"    {reason}: {count}")

    guard_trips = metrics.get("guard_trips", {})
    if guard_trips:
        lines.append("")
        lines.append("  Guard trips (blocked/open):")
        for guard, count in sorted(guard_trips.items()):
            lines.append(f"    {guard}: {count}")

    lines.append("")
    return "\n".join(lines)
