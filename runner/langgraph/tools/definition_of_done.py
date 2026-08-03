"""Definition of Done enforcement gate.

Validates that a completed worker run demonstrates the task is truly done.
Checks five conditions against the parsed worker summary and raw worker output:

1. files_touched      — at least one file was created or modified
2. check_not_failed   — worker did not explicitly report check.sh as failed
3. output_present     — worker produced meaningful output (above a minimum length)
4. success_evidence   — when the task defines acceptance_criteria.success_evidence,
                        the worker output references it (keyword match)
5. file_claims_exist  — every file the worker claims to have created or modified
                        actually exists in the working tree or the diff; a
                        mismatch is flagged as issue type ``dod_file_claim_mismatch``

Gate behaviour (controlled from config.py):
- DEFINITION_OF_DONE_GATE_ENABLED=true (default): validates every completed run
- DEFINITION_OF_DONE_STRICT_MODE=false (default): DoD failure is logged as a
  warning and the loop continues; set to true to mark the task failed and halt.
"""
import os
import re
from tools.independent_code_review import _extract_changed_files
from tools.log_tools import log_event

DOD_FILE_CLAIM_MISMATCH = "dod_file_claim_mismatch"

_MIN_OUTPUT_LENGTH = 50  # credible worker output is not a few words

_EMPTY_VALUES = frozenset({"", "none", "n/a", "na", "(none)", "not applicable", "skipped"})


def _meaningful_items(items: list) -> list[str]:
    return [str(v).strip() for v in items if str(v).strip().lower() not in _EMPTY_VALUES]


def _check_files_touched(summary: dict) -> tuple[bool, str]:
    created = _meaningful_items(summary.get("files_created") or [])
    modified = _meaningful_items(summary.get("files_modified") or [])
    if created or modified:
        return True, ""
    return False, "no files created or modified reported in worker output"


def _check_file_claims_exist(summary: dict, repo_path: str, diff_text: str) -> tuple[bool, str]:
    """Fail when a claimed file is neither on disk nor present in the diff.

    A worker can claim to have created or modified a file it never actually
    touched (M0.9 finding). This cross-references every claimed path against
    the working tree first, then the diff, so a file that was created and
    later removed (but still shows up in the diff) is not flagged.

    Skipped entirely when no ``repo_path`` is supplied — callers that don't
    wire in a repo (e.g. existing unit tests) get the same behaviour as before.
    """
    if not repo_path:
        return True, ""

    claimed = _meaningful_items(
        (summary.get("files_created") or []) + (summary.get("files_modified") or [])
    )
    if not claimed:
        return True, ""

    diff_files = set(_extract_changed_files(diff_text or ""))

    missing = []
    for raw_path in claimed:
        rel_path = raw_path.lstrip("./")
        if rel_path in diff_files:
            continue
        if os.path.exists(os.path.join(repo_path, rel_path)):
            continue
        missing.append(raw_path)

    if missing:
        return False, (
            f"{DOD_FILE_CLAIM_MISMATCH}: claimed file(s) not found in working "
            f"tree or diff: {', '.join(missing)}"
        )
    return True, ""


def _check_not_failed(summary: dict) -> tuple[bool, str]:
    if summary.get("check_result") is False:
        return False, "worker reported check result as failed"
    return True, ""


def _check_output_present(raw_output: str) -> tuple[bool, str]:
    if len(raw_output.strip()) >= _MIN_OUTPUT_LENGTH:
        return True, ""
    return False, (
        f"worker output is too short to be credible "
        f"({len(raw_output.strip())} chars, minimum {_MIN_OUTPUT_LENGTH})"
    )


def _check_success_evidence(raw_output: str, task: dict) -> tuple[bool, str]:
    ac = task.get("acceptance_criteria")
    if not isinstance(ac, dict):
        return True, ""

    evidence = ac.get("success_evidence", "")
    if not evidence or not str(evidence).strip():
        return True, ""

    evidence_str = str(evidence).strip()
    keywords = [w.lower() for w in re.findall(r'\b[a-zA-Z][a-zA-Z]{3,}\b', evidence_str)]
    if not keywords:
        return True, ""

    output_lower = raw_output.lower()
    matched = [kw for kw in keywords if kw in output_lower]
    threshold = max(1, len(keywords) // 2)
    if len(matched) >= threshold:
        return True, ""

    return False, (
        f"worker output does not reference task success evidence "
        f"(matched {len(matched)}/{len(keywords)} keywords "
        f"from: '{evidence_str[:100]}')"
    )


def validate_definition_of_done(
    summary: dict,
    task: dict,
    raw_output: str = "",
    repo_path: str = "",
    diff_text: str = "",
) -> tuple[bool, list[str]]:
    """Check whether a worker run meets the task's definition of done.

    Returns (ok, issues) where issues is empty when ok is True.
    """
    checks = [
        _check_files_touched(summary),
        _check_not_failed(summary),
        _check_output_present(raw_output),
        _check_success_evidence(raw_output, task),
        _check_file_claims_exist(summary, repo_path, diff_text),
    ]
    issues = [msg for ok, msg in checks if not ok]
    return len(issues) == 0, issues


def guard_definition_of_done(
    summary: dict,
    task: dict,
    raw_output: str = "",
    context: str = "",
    *,
    strict_mode: bool = False,
    repo_path: str = "",
    diff_text: str = "",
) -> dict:
    """Run the DoD gate and log the result.

    Returns a dict with:
    - ``passed`` (bool): True when all checks pass.
    - ``issues`` (list[str]): reasons for failure; empty when passed.
    - ``strict_mode`` (bool): mirrors the input flag.

    Logs ``task_definition_of_done_passed`` on success, or
    ``task_definition_of_done_rejected`` (strict mode) /
    ``task_definition_of_done_warned`` (non-strict) on failure.
    """
    ok, issues = validate_definition_of_done(summary, task, raw_output, repo_path, diff_text)
    task_id = task.get("id")

    if ok:
        log_event("task_definition_of_done_passed", {
            "task_id": task_id,
            "context": context,
        }, task_id=task_id)
        return {"passed": True, "issues": [], "strict_mode": strict_mode}

    if strict_mode:
        log_event("task_definition_of_done_rejected", {
            "task_id": task_id,
            "task_title": task.get("title"),
            "issues": issues,
            "context": context,
            "strict_mode": True,
        }, task_id=task_id)
    else:
        log_event("task_definition_of_done_warned", {
            "task_id": task_id,
            "task_title": task.get("title"),
            "issues": issues,
            "context": context,
            "strict_mode": False,
        }, task_id=task_id)

    return {"passed": False, "issues": issues, "strict_mode": strict_mode}
