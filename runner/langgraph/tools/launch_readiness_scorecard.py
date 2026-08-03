"""Launch Readiness Scorecard.

Scores the runner system's readiness to operate by evaluating four dimensions:

1. config_completeness   (weight 0.25) — required settings are populated
2. credentials_available (weight 0.25) — API keys / tokens are configured
3. safety_gates_active   (weight 0.25) — critical safety features are enabled
4. operational_health    (weight 0.25) — no active stop_reason or failure streak

Overall weighted score in [0.0, 1.0]. Passes when score >= threshold (default 0.7).

Gate behaviour (controlled from config.py):
- LAUNCH_READINESS_SCORECARD_ENABLED=true (default): scores on every loop start
- LAUNCH_READINESS_SCORECARD_STRICT_MODE=false (default): a low score is logged as
  a warning and the loop continues; set to true to halt when the score is too low.
- LAUNCH_READINESS_SCORECARD_PASS_THRESHOLD=0.7 (default): minimum score to pass
"""
from __future__ import annotations

from tools.log_tools import log_event

_PASS_THRESHOLD_DEFAULT = 0.7


def _score_config_completeness(config_snapshot: dict) -> tuple[float, str]:
    """Score based on whether critical config fields are populated."""
    issues: list[str] = []
    score = 1.0

    if not config_snapshot.get("repo_path"):
        issues.append("BUCKS_AI_REPO_PATH not set")
        score -= 0.4

    if (config_snapshot.get("max_loop_tasks") or 0) <= 0:
        issues.append("MAX_LOOP_TASKS is 0 or negative")
        score -= 0.2

    if (config_snapshot.get("max_runtime_minutes") or 0) <= 0:
        issues.append("MAX_RUNTIME_MINUTES is 0 or negative")
        score -= 0.2

    if (config_snapshot.get("max_consecutive_failures") or 0) <= 0:
        issues.append("MAX_CONSECUTIVE_FAILURES is 0 or negative")
        score -= 0.1

    if (config_snapshot.get("max_task_retries") or 0) < 0:
        issues.append("MAX_TASK_RETRIES is negative")
        score -= 0.1

    score = max(0.0, score)
    if not issues:
        return score, "all critical config fields are populated"
    return score, "; ".join(issues)


def _score_credentials_available(config_snapshot: dict) -> tuple[float, str]:
    """Score based on how many useful credentials are configured."""
    credentials = [
        ("OpenAI / ChatGPT", bool(config_snapshot.get("openai"))),
        ("Anthropic / Claude", bool(config_snapshot.get("anthropic"))),
        ("GitHub token", bool(config_snapshot.get("github"))),
        ("Supabase", bool(config_snapshot.get("supabase"))),
        ("Vercel", bool(config_snapshot.get("vercel"))),
    ]

    available = [name for name, ok in credentials if ok]
    missing = [name for name, ok in credentials if not ok]
    total = len(credentials)
    count = len(available)

    score = count / total if total > 0 else 1.0

    if not missing:
        return round(score, 3), f"all {total} credentials configured"
    return round(score, 3), (
        f"{count}/{total} credentials configured; missing: {', '.join(missing)}"
    )


def _score_safety_gates_active(config_snapshot: dict) -> tuple[float, str]:
    """Score based on whether critical safety features are enabled."""
    critical_gates = [
        ("failure_guard", config_snapshot.get("failure_guard_enabled", True)),
        ("resource_gate", config_snapshot.get("resource_gate_enabled", True)),
        ("acceptance_criteria_gate", config_snapshot.get("acceptance_criteria_gate_enabled", True)),
    ]
    optional_gates = [
        ("independent_code_review", config_snapshot.get("independent_code_review_enabled", True)),
        ("auto_repair_loop", config_snapshot.get("auto_repair_loop_enabled", True)),
        ("risk_based_merge_approval", config_snapshot.get("risk_based_merge_approval_enabled", True)),
    ]

    critical_off = [name for name, enabled in critical_gates if not enabled]
    optional_off = [name for name, enabled in optional_gates if not enabled]

    score = 1.0
    score -= 0.25 * len(critical_off)
    score -= 0.05 * len(optional_off)
    score = max(0.0, score)

    notes: list[str] = []
    if not critical_off and not optional_off:
        notes.append("all safety gates active")
    if critical_off:
        notes.append(f"CRITICAL gates disabled: {', '.join(critical_off)}")
    if optional_off:
        notes.append(f"optional gates disabled: {', '.join(optional_off)}")

    return round(score, 3), "; ".join(notes)


def _score_operational_health(state_snapshot: dict) -> tuple[float, str]:
    """Score based on the current loop state health metrics."""
    if not state_snapshot:
        return 0.8, "no prior run state available (first launch)"

    score = 1.0
    issues: list[str] = []

    stop_reason = state_snapshot.get("stop_reason")
    if stop_reason:
        score -= 0.3
        issues.append(f"active stop_reason from previous run: {stop_reason}")

    consecutive_failures = int(state_snapshot.get("consecutive_failures") or 0)
    if consecutive_failures >= 2:
        score -= 0.2
        issues.append(f"{consecutive_failures} consecutive failures in last run")
    elif consecutive_failures == 1:
        score -= 0.05
        issues.append("1 consecutive failure in last run")

    worker_timeout_count = int(state_snapshot.get("worker_timeout_count") or 0)
    if worker_timeout_count >= 3:
        score -= 0.2
        issues.append(f"{worker_timeout_count} worker timeouts this session")
    elif worker_timeout_count >= 1:
        score -= 0.1
        issues.append(f"{worker_timeout_count} worker timeout(s) this session")

    score = max(0.0, score)
    if not issues:
        return round(score, 3), "loop state is healthy"
    return round(score, 3), "; ".join(issues)


def score_launch_readiness_dimensions(
    config_snapshot: dict,
    state_snapshot: dict,
) -> list[dict]:
    """Return per-dimension scores for the runner launch readiness.

    Each dict has: name (str), weight (float), score (float), rationale (str).
    """
    scorers: list[tuple[str, float]] = [
        ("config_completeness", 0.25),
        ("credentials_available", 0.25),
        ("safety_gates_active", 0.25),
        ("operational_health", 0.25),
    ]
    raw_scores = [
        _score_config_completeness(config_snapshot),
        _score_credentials_available(config_snapshot),
        _score_safety_gates_active(config_snapshot),
        _score_operational_health(state_snapshot),
    ]
    return [
        {
            "name": name,
            "weight": weight,
            "score": score,
            "rationale": rationale,
        }
        for (name, weight), (score, rationale) in zip(scorers, raw_scores)
    ]


def evaluate_launch_readiness(
    dimension_scores: list[dict],
    pass_threshold: float = _PASS_THRESHOLD_DEFAULT,
) -> dict:
    """Aggregate dimension scores into an overall evaluation dict.

    Returns:
        overall_score    — weighted average in [0.0, 1.0]
        passed           — True when overall_score >= pass_threshold
        pass_threshold   — the threshold used
        dimension_scores — echoed from the input
    """
    if not dimension_scores:
        return {
            "overall_score": 1.0,
            "passed": True,
            "pass_threshold": pass_threshold,
            "dimension_scores": [],
        }

    total_weight = sum(d["weight"] for d in dimension_scores)
    overall = (
        sum(d["score"] * d["weight"] for d in dimension_scores) / total_weight
        if total_weight > 0
        else 0.0
    )
    overall = round(overall, 3)
    return {
        "overall_score": overall,
        "passed": overall >= pass_threshold,
        "pass_threshold": pass_threshold,
        "dimension_scores": dimension_scores,
    }


def format_scorecard_report(evaluation: dict) -> str:
    """Return a human-readable launch readiness scorecard report string."""
    overall_score = evaluation["overall_score"]
    passed = evaluation["passed"]
    threshold = evaluation["pass_threshold"]
    status = "READY" if passed else "NOT READY"

    header = (
        f"Launch Readiness Scorecard\n"
        f"Status: {status}  Score: {overall_score:.2f} / {threshold:.2f} threshold\n"
    )
    lines = [header]
    for d in evaluation.get("dimension_scores", []):
        icon = "+" if d["score"] >= threshold else ("-" if d["score"] < 0.4 else "~")
        lines.append(
            f"  [{icon}] {d['name']:<28} {d['score']:.2f}"
            f"  (weight {d['weight']:.2f})  — {d['rationale']}"
        )
    return "\n".join(lines) + "\n"


def run_launch_readiness_scorecard(
    config_snapshot: dict,
    state_snapshot: dict,
    pass_threshold: float = _PASS_THRESHOLD_DEFAULT,
) -> dict:
    """Score runner launch readiness across all dimensions.

    Returns:
        overall_score    — weighted average in [0.0, 1.0]
        passed           — True when overall_score >= pass_threshold
        pass_threshold   — the threshold used
        dimension_scores — per-dimension score dicts
        report           — human-readable scorecard string
    """
    dimension_scores = score_launch_readiness_dimensions(config_snapshot, state_snapshot)
    evaluation = evaluate_launch_readiness(dimension_scores, pass_threshold)
    report = format_scorecard_report(evaluation)
    return {**evaluation, "report": report}


def guard_launch_readiness(
    config_snapshot: dict,
    state_snapshot: dict,
    pass_threshold: float = _PASS_THRESHOLD_DEFAULT,
    *,
    strict_mode: bool = False,
    context: str = "",
) -> dict:
    """Run the launch readiness scorecard gate and log the result.

    Returns a dict with:
    - passed          (bool): True when overall_score >= pass_threshold.
    - overall_score   (float): weighted average score.
    - dimension_scores (list): per-dimension breakdowns.
    - report          (str): human-readable scorecard.
    - strict_mode     (bool): mirrors the input flag.

    Logs ``launch_readiness_passed`` on success, or
    ``launch_readiness_failed`` (strict) /
    ``launch_readiness_warned`` (non-strict) on failure.
    """
    evaluation = run_launch_readiness_scorecard(config_snapshot, state_snapshot, pass_threshold)

    if evaluation["passed"]:
        log_event("launch_readiness_passed", {
            "overall_score": evaluation["overall_score"],
            "pass_threshold": pass_threshold,
            "context": context,
        })
    elif strict_mode:
        log_event("launch_readiness_failed", {
            "overall_score": evaluation["overall_score"],
            "pass_threshold": pass_threshold,
            "dimension_scores": evaluation["dimension_scores"],
            "context": context,
            "strict_mode": True,
        })
    else:
        log_event("launch_readiness_warned", {
            "overall_score": evaluation["overall_score"],
            "pass_threshold": pass_threshold,
            "dimension_scores": evaluation["dimension_scores"],
            "context": context,
            "strict_mode": False,
        })

    return {
        "passed": evaluation["passed"],
        "overall_score": evaluation["overall_score"],
        "dimension_scores": evaluation["dimension_scores"],
        "report": evaluation["report"],
        "strict_mode": strict_mode,
    }
