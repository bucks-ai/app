"""Validates that tasks include concrete acceptance criteria before execution.

Checks for five required criteria:
- allowed_scope: files or areas the task is permitted to touch
- forbidden_scope: what the task must NOT modify
- required_checks: test/validation expectations
- success_evidence: what proves the task is done
- rollback_behavior: what happens if the task fails

Additionally recognises an optional boolean field:
- human_approval_required: whether explicit human sign-off is needed

Primary method: checks the task's ``acceptance_criteria`` dict field.
Fallback method: keyword-scans the task's ``description`` field.

Gate behaviour (controlled from config.py):
- ACCEPTANCE_CRITERIA_GATE_ENABLED=true (default): validates every task
- ACCEPTANCE_CRITERIA_STRICT_MODE=false (default): missing criteria logged
  as a warning but task proceeds; set to true to block task execution
"""
import re
from tools.log_tools import log_event

_REQUIRED_AC_KEYS: tuple[str, ...] = (
    "allowed_scope",
    "forbidden_scope",
    "required_checks",
    "success_evidence",
    "rollback_behavior",
)

# Description keyword patterns used as a fallback when no structured
# ``acceptance_criteria`` dict is present. At least one pattern per criterion
# must match for that criterion to be considered present.
_CRITERIA_PATTERNS: dict[str, list[re.Pattern]] = {
    "allowed_scope": [
        re.compile(r'\ballowed\s+scope\b', re.IGNORECASE),
        re.compile(r'\bexpected\s+files?\b', re.IGNORECASE),
        re.compile(r'\bfiles?\s+(created|modified|allowed)\b', re.IGNORECASE),
        re.compile(r'\bpermitted\s+(to\s+)?(touch|modify|create)\b', re.IGNORECASE),
    ],
    "forbidden_scope": [
        re.compile(r'\bforbidden\s+scope\b', re.IGNORECASE),
        re.compile(r'\bmust\s+not\s+(touch|modify|change)\b', re.IGNORECASE),
        re.compile(r'\bdo\s+not\s+(modify|touch|change)\b', re.IGNORECASE),
        re.compile(r'\boff[- ]limits?\b', re.IGNORECASE),
        re.compile(r'\bforbidden\s*:', re.IGNORECASE),
    ],
    "required_checks": [
        re.compile(r'\brequired\s+checks?\b', re.IGNORECASE),
        re.compile(r'\btest\s+expectations?\b', re.IGNORECASE),
        re.compile(r'\bmust\s+pass\b', re.IGNORECASE),
        re.compile(r'\brequired\s+tests?\b', re.IGNORECASE),
        re.compile(r'\bcheck\.sh\b', re.IGNORECASE),
    ],
    "success_evidence": [
        re.compile(r'\bsuccess\s+evidence\b', re.IGNORECASE),
        re.compile(r'\bdone\s+(condition|when|criteria)\b', re.IGNORECASE),
        re.compile(r'\bevidence\s+of\s+(completion|success)\b', re.IGNORECASE),
        re.compile(r'\bsuccess\s+criteria\b', re.IGNORECASE),
        re.compile(r'\bproven?\s+(complete|done)\b', re.IGNORECASE),
    ],
    "rollback_behavior": [
        re.compile(r'\brollback\b', re.IGNORECASE),
        re.compile(r'\bfailure\s+behavior\b', re.IGNORECASE),
        re.compile(r'\bon\s+fail(ure)?\b', re.IGNORECASE),
        re.compile(r'\bif\s+(it\s+)?fails?\b', re.IGNORECASE),
    ],
}


def validate_acceptance_criteria(task: dict) -> tuple[bool, list[str]]:
    """Check whether a task has concrete acceptance criteria.

    Checks the structured ``acceptance_criteria`` dict field first; falls back
    to keyword-scanning ``description`` for each required criterion.

    Returns ``(ok, issues)`` where ``issues`` is empty when ``ok`` is True.
    """
    issues: list[str] = []

    ac = task.get("acceptance_criteria")

    if isinstance(ac, dict):
        for key in _REQUIRED_AC_KEYS:
            val = ac.get(key)
            if not val or (isinstance(val, str) and not val.strip()):
                issues.append(f"acceptance_criteria.{key} is missing or empty")
            elif isinstance(val, list) and not any(str(v).strip() for v in val):
                issues.append(f"acceptance_criteria.{key} list is empty")
        return len(issues) == 0, issues

    # Fallback: keyword scan on description.
    description = task.get("description", "")
    if not description or not description.strip():
        for key in _REQUIRED_AC_KEYS:
            issues.append(f"no description and no acceptance_criteria.{key}")
        return False, issues

    for key, patterns in _CRITERIA_PATTERNS.items():
        if not any(p.search(description) for p in patterns):
            issues.append(f"description missing '{key}' criterion")

    return len(issues) == 0, issues


def guard_acceptance_criteria(
    task: dict,
    context: str = "",
    *,
    strict_mode: bool = False,
) -> dict:
    """Validate acceptance criteria and return a gate decision dict.

    Returns a dict with:
    - ``passed`` (bool): True when all required criteria are present.
    - ``issues`` (list[str]): reasons for rejection; empty when passed.
    - ``strict_mode`` (bool): mirrors the input flag.

    Logs ``task_acceptance_criteria_passed`` on success, or
    ``task_acceptance_criteria_rejected`` (strict mode) /
    ``task_acceptance_criteria_warned`` (non-strict) on failure.
    """
    ok, issues = validate_acceptance_criteria(task)
    task_id = task.get("id")

    if ok:
        log_event("task_acceptance_criteria_passed", {
            "task_id": task_id,
            "context": context,
        }, task_id=task_id)
        return {"passed": True, "issues": [], "strict_mode": strict_mode}

    if strict_mode:
        log_event("task_acceptance_criteria_rejected", {
            "task_id": task_id,
            "task_title": task.get("title"),
            "issues": issues,
            "context": context,
            "strict_mode": True,
        }, task_id=task_id)
    else:
        log_event("task_acceptance_criteria_warned", {
            "task_id": task_id,
            "task_title": task.get("title"),
            "issues": issues,
            "context": context,
            "strict_mode": False,
        }, task_id=task_id)

    return {"passed": False, "issues": issues, "strict_mode": strict_mode}
