"""Business Output Evaluation Rubrics.

Scores completed worker runs across four business-quality dimensions:

1. functional_correctness   (weight 0.30) — check_result + files touched
2. business_value_alignment (weight 0.25) — keyword overlap with task goal
3. completeness             (weight 0.25) — file count, credentials, limitations
4. risk_awareness           (weight 0.20) — credential hygiene, no security red flags

Overall weighted score in [0.0, 1.0]. Passes when score >= threshold (default 0.6).

Gate behaviour (controlled from config.py):
- BUSINESS_OUTPUT_RUBRICS_ENABLED=true (default): scores every completed run
- BUSINESS_OUTPUT_RUBRICS_STRICT_MODE=false (default): a low score is logged as
  a warning and the loop continues; set to true to block the task.
- BUSINESS_OUTPUT_RUBRICS_PASS_THRESHOLD=0.6 (default): minimum overall score to pass
"""
from __future__ import annotations

import re
from tools.log_tools import log_event

_PASS_THRESHOLD_DEFAULT = 0.6
_KEYWORD_MIN_LENGTH = 4

_EMPTY_VALUES = frozenset({"", "none", "n/a", "na", "(none)", "not applicable", "skipped"})

# Security red-flag patterns: credential values embedded in output text
_RED_FLAG_PATTERNS: list[re.Pattern] = [
    re.compile(
        r'(password|passwd|secret|api[_\-]?key|token)\s*[=:]\s*\S{6,}',
        re.IGNORECASE,
    ),
    re.compile(r'\b(sk|pk|rk)-[a-zA-Z0-9]{20,}\b'),
    re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'),
]


def _is_empty(val) -> bool:
    if val is None:
        return True
    return str(val).strip().lower() in _EMPTY_VALUES


def _meaningful_items(items) -> list[str]:
    if not items:
        return []
    return [str(v).strip() for v in items if not _is_empty(v)]


def _score_functional_correctness(summary: dict) -> tuple[float, str]:
    """Score based on check_result and whether any files were touched."""
    check_result = summary.get("check_result")
    created = _meaningful_items(summary.get("files_created") or [])
    modified = _meaningful_items(summary.get("files_modified") or [])
    files_touched = bool(created or modified)

    if check_result is False:
        return 0.0, "check_result reported as failed"
    if check_result is True:
        if files_touched:
            return 1.0, "check passed and files were created or modified"
        return 0.6, "check passed but no files reported as changed"
    # check_result is None / unknown
    if files_touched:
        return 0.7, "check result unknown but files were touched"
    return 0.3, "check result unknown and no files reported as changed"


def _score_business_value_alignment(
    summary: dict,  # noqa: ARG001
    task: dict,
    raw_output: str,
) -> tuple[float, str]:
    """Score based on keyword overlap between the task goal and the worker output."""
    task_text = " ".join(filter(None, [
        task.get("title", ""),
        task.get("description", ""),
    ]))

    if not task_text.strip():
        return 0.8, "no task description to align against (assumed adequate)"

    keywords = list(dict.fromkeys(
        w.lower()
        for w in re.findall(
            r'\b[a-zA-Z][a-zA-Z]{' + str(_KEYWORD_MIN_LENGTH - 1) + r',}\b',
            task_text,
        )
    ))

    if not keywords:
        return 0.8, "task contains no scorable keywords (assumed adequate)"

    output_lower = raw_output.lower()
    matched = [kw for kw in keywords if kw in output_lower]
    score = min(len(matched) / len(keywords), 1.0)
    return score, f"matched {len(matched)}/{len(keywords)} task keywords in output"


def _score_completeness(summary: dict) -> tuple[float, str]:
    """Score based on files touched, credentials needed, and known limitations."""
    score = 0.5
    notes: list[str] = []

    created = _meaningful_items(summary.get("files_created") or [])
    modified = _meaningful_items(summary.get("files_modified") or [])
    if created or modified:
        score += 0.3
        notes.append(f"{len(created) + len(modified)} file(s) touched")
    else:
        notes.append("no files reported")

    creds = _meaningful_items(summary.get("credentials_needed") or [])
    if not creds:
        score += 0.1
        notes.append("no credentials blocked")
    else:
        score -= 0.1
        notes.append(f"{len(creds)} credential(s) needed")

    limits = _meaningful_items(summary.get("known_limitations") or [])
    if not limits:
        score += 0.1
        notes.append("no known limitations")
    else:
        score -= 0.1
        notes.append(f"{len(limits)} known limitation(s)")

    return max(0.0, min(1.0, score)), "; ".join(notes)


def _score_risk_awareness(
    summary: dict,  # noqa: ARG001
    raw_output: str,
) -> tuple[float, str]:
    """Score based on absence of security red flags in the worker output."""
    score = 1.0
    issues: list[str] = []

    for pattern in _RED_FLAG_PATTERNS:
        if pattern.search(raw_output):
            score -= 0.4
            issues.append(f"possible credential exposure ({pattern.pattern[:40]})")

    score = max(0.0, score)
    if not issues:
        return score, "no security red flags detected"
    return score, "; ".join(issues)


def score_rubric_dimensions(
    summary: dict,
    task: dict,
    raw_output: str = "",
) -> list[dict]:
    """Return per-dimension scores for a worker output.

    Each dict has: name (str), weight (float), score (float), rationale (str).
    """
    scorers: list[tuple[str, float]] = [
        ("functional_correctness", 0.30),
        ("business_value_alignment", 0.25),
        ("completeness", 0.25),
        ("risk_awareness", 0.20),
    ]
    raw_scores = [
        _score_functional_correctness(summary),
        _score_business_value_alignment(summary, task, raw_output),
        _score_completeness(summary),
        _score_risk_awareness(summary, raw_output),
    ]
    return [
        {
            "name": name,
            "weight": weight,
            "score": round(score, 3),
            "rationale": rationale,
        }
        for (name, weight), (score, rationale) in zip(scorers, raw_scores)
    ]


def evaluate_rubric_scores(
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


def format_rubric_report(evaluation: dict, task: dict) -> str:
    """Return a human-readable rubric evaluation report string."""
    task_id = task.get("id", "unknown")
    task_title = task.get("title", "")
    overall_score = evaluation["overall_score"]
    passed = evaluation["passed"]
    threshold = evaluation["pass_threshold"]
    status = "PASSED" if passed else "FAILED"

    header = (
        f"Business Output Rubric — task {task_id}"
        + (f" ({task_title})" if task_title else "")
        + f"\nStatus: {status}  Score: {overall_score:.2f} / {threshold:.2f} threshold\n"
    )
    lines = [header]
    for d in evaluation.get("dimension_scores", []):
        icon = "+" if d["score"] >= threshold else ("-" if d["score"] < 0.4 else "~")
        lines.append(
            f"  [{icon}] {d['name']:<28} {d['score']:.2f}"
            f"  (weight {d['weight']:.2f})  — {d['rationale']}"
        )
    return "\n".join(lines) + "\n"


def evaluate_business_output(
    summary: dict,
    task: dict,
    raw_output: str = "",
    pass_threshold: float = _PASS_THRESHOLD_DEFAULT,
) -> dict:
    """Score worker output against all rubric dimensions and return a full evaluation.

    Returns:
        overall_score    — weighted average in [0.0, 1.0]
        passed           — True when overall_score >= pass_threshold
        pass_threshold   — the threshold used
        dimension_scores — per-dimension score dicts
        report           — human-readable string report
    """
    dimension_scores = score_rubric_dimensions(summary, task, raw_output)
    evaluation = evaluate_rubric_scores(dimension_scores, pass_threshold)
    report = format_rubric_report(evaluation, task)
    return {**evaluation, "report": report}


def guard_business_output(
    summary: dict,
    task: dict,
    raw_output: str = "",
    context: str = "",
    pass_threshold: float = _PASS_THRESHOLD_DEFAULT,
    *,
    strict_mode: bool = False,
) -> dict:
    """Run the business output rubric gate and log the result.

    Returns a dict with:
    - passed          (bool): True when overall_score >= pass_threshold.
    - overall_score   (float): weighted average score.
    - dimension_scores (list): per-dimension breakdowns.
    - report          (str): human-readable report.
    - strict_mode     (bool): mirrors the input flag.

    Logs ``business_output_rubric_passed`` on success, or
    ``business_output_rubric_rejected`` (strict) /
    ``business_output_rubric_warned`` (non-strict) on failure.
    """
    evaluation = evaluate_business_output(summary, task, raw_output, pass_threshold)
    task_id = task.get("id")

    if evaluation["passed"]:
        log_event("business_output_rubric_passed", {
            "task_id": task_id,
            "overall_score": evaluation["overall_score"],
            "pass_threshold": pass_threshold,
            "context": context,
        }, task_id=task_id)
    elif strict_mode:
        log_event("business_output_rubric_rejected", {
            "task_id": task_id,
            "task_title": task.get("title"),
            "overall_score": evaluation["overall_score"],
            "pass_threshold": pass_threshold,
            "dimension_scores": evaluation["dimension_scores"],
            "context": context,
            "strict_mode": True,
        }, task_id=task_id)
    else:
        log_event("business_output_rubric_warned", {
            "task_id": task_id,
            "task_title": task.get("title"),
            "overall_score": evaluation["overall_score"],
            "pass_threshold": pass_threshold,
            "dimension_scores": evaluation["dimension_scores"],
            "context": context,
            "strict_mode": False,
        }, task_id=task_id)

    return {
        "passed": evaluation["passed"],
        "overall_score": evaluation["overall_score"],
        "dimension_scores": evaluation["dimension_scores"],
        "report": evaluation["report"],
        "strict_mode": strict_mode,
    }
