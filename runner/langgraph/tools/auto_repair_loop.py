"""Auto-Repair Loop v2.

When check.sh fails after a successful worker run, re-dispatch the same worker
with the check failure output so it can fix the issues in place.  The loop runs
up to MAX_AUTO_REPAIR_ATTEMPTS times before giving up and letting the normal
failure guard handle the task.

Gate behaviour (controlled via config.py / env vars):
- AUTO_REPAIR_LOOP_ENABLED=true  (default): auto-repair is active.
- MAX_AUTO_REPAIR_ATTEMPTS=2     (default): maximum repair attempts per task.

Deterministic-Failure Repair (M4c.4):
- MAX_REPAIR_DEPTH=3             (default): max repair depth per task.

Transient failures (network, cooldown, timeout) are never routed here —
they keep the retry-with-backoff path unchanged.
"""
import hashlib
import json
import subprocess
from typing import Optional

# ---------------------------------------------------------------------------
# Failure class constants (used as routing keys)
# ---------------------------------------------------------------------------

CI_CHECK_FAILURE = "ci_check_failure"
MERGE_CONFLICT = "merge_conflict"
COMPLETION_EVIDENCE_BLOCK = "completion_evidence_block"
GATE_BLOCK = "gate_block"

# Markers used to detect CI failures from worker_result.error
_CI_MARKER = "pr_checks_failed:"
# Markers and keywords for merge conflict detection
_CONFLICT_MARKERS = ("pr_merge_failed:",)
_CONFLICT_KEYWORDS = ("conflict",)


# ---------------------------------------------------------------------------
# Original check.sh repair (v2)
# ---------------------------------------------------------------------------


def should_auto_repair(
    worker_result: dict,
    check_passed: "bool | None",
    auto_repair_attempt: int,
    max_attempts: int,
) -> bool:
    """True when conditions are met for a check.sh repair attempt.

    Returns False when:
    - The worker itself failed (let the failure guard handle it).
    - Checks already passed (no repair needed).
    - All repair attempts have been used.
    """
    if not worker_result.get("success", False):
        return False
    if check_passed:
        return False
    if auto_repair_attempt >= max_attempts:
        return False
    return True


def build_auto_repair_prompt(
    original_prompt: str,
    check_output: str,
    task: dict,
    attempt: int,
    max_attempts: int,
) -> str:
    """Build a repair prompt describing why check.sh failed.

    Includes the check.sh output so the worker can target the specific failures,
    followed by the original task prompt verbatim for full context.
    """
    truncated_output = (
        check_output[:3000] + "\n... (truncated)"
        if len(check_output) > 3000
        else check_output
    )
    return (
        f"The task was completed but check.sh failed "
        f"(repair attempt {attempt} of {max_attempts}).\n"
        "Your job is to fix the issues reported below and re-run the checks.\n\n"
        f"check.sh output:\n{truncated_output}\n\n"
        "--- ORIGINAL TASK ---\n"
        f"{original_prompt}"
    )


# ---------------------------------------------------------------------------
# Deterministic failure classification
# ---------------------------------------------------------------------------


def classify_deterministic_failure(error: str) -> Optional[str]:
    """Classify a worker error string as a deterministic failure class.

    Returns None for transient or unclassifiable failures; these take the
    normal retry-with-backoff path unchanged.
    """
    if not error:
        return None
    lower = error.lower()
    if _CI_MARKER in lower:
        return CI_CHECK_FAILURE
    if any(m in lower for m in _CONFLICT_MARKERS) and any(k in lower for k in _CONFLICT_KEYWORDS):
        return MERGE_CONFLICT
    return None


# ---------------------------------------------------------------------------
# Failure signature (identical-repeat detection)
# ---------------------------------------------------------------------------


def make_failure_signature(failure_class: str, evidence: dict) -> str:
    """Create a short stable fingerprint for a failure.

    Two failures with the same class + evidence produce the same signature.
    This lets the repair loop detect when it has produced the exact same
    failure twice and stop rather than looping.
    """
    key: dict = {"class": failure_class}
    if failure_class == CI_CHECK_FAILURE:
        key["failed"] = sorted(evidence.get("failed_checks") or [])
    elif failure_class == MERGE_CONFLICT:
        key["files"] = sorted(evidence.get("conflicted_files") or [])
    elif failure_class == COMPLETION_EVIDENCE_BLOCK:
        key["reasons"] = sorted(evidence.get("reasons") or [])
    elif failure_class == GATE_BLOCK:
        key["gate"] = evidence.get("gate", "")
        key["reasons"] = sorted(evidence.get("reasons") or [])
    data = json.dumps(key, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Repair budget guard
# ---------------------------------------------------------------------------


def should_deterministic_repair(
    repair_depth: int,
    max_repair_depth: int,
    last_signature: Optional[str],
    current_signature: Optional[str],
) -> tuple:
    """Return (should_repair: bool, reason: str).

    Stops if:
    - repair_depth >= max_repair_depth → ('False', 'depth_exceeded')
    - last_signature == current_signature → ('False', 'repeated_signature')
    Otherwise returns (True, 'ok').
    """
    if repair_depth >= max_repair_depth:
        return False, "depth_exceeded"
    if last_signature and current_signature and last_signature == current_signature:
        return False, "repeated_signature"
    return True, "ok"


# ---------------------------------------------------------------------------
# Evidence fetchers
# ---------------------------------------------------------------------------


def fetch_ci_failure_evidence(
    check_runs: list,
    repo: str,
    token: str,
    max_excerpt_chars: int = 2000,
) -> dict:
    """Build a CI failure evidence dict from check run data.

    Extracts failed check names, GitHub output summaries, and (best-effort)
    per-run annotations via the GitHub REST API.  Degrades gracefully when the
    token or network is absent.
    """
    failed = [
        r for r in (check_runs or [])
        if r.get("conclusion") not in ("success", "skipped", None)
    ]

    evidence: dict = {
        "failed_checks": [r.get("name") for r in failed],
        "conclusions": {r.get("name"): r.get("conclusion") for r in failed},
        "log_excerpt": "",
    }

    parts: list = []
    chars_used = 0

    for run in failed[:3]:  # cap at 3 check runs to limit prompt size
        check_name = run.get("name", "unknown")
        output = run.get("output") or {}
        summary = (output.get("summary") or "").strip()
        text = (output.get("text") or "").strip()

        if summary and chars_used < max_excerpt_chars:
            chunk = f"[{check_name}] {summary}"[: max_excerpt_chars - chars_used]
            parts.append(chunk)
            chars_used += len(chunk)

        if text and chars_used < max_excerpt_chars:
            chunk = f"[{check_name} output] {text}"[: max_excerpt_chars - chars_used]
            parts.append(chunk)
            chars_used += len(chunk)

        # Fetch per-run annotations from the GitHub API
        run_id = run.get("id")
        if run_id and repo and token and chars_used < max_excerpt_chars:
            try:
                import requests as _req  # lazy import — not available in tests without mock
                r = _req.get(
                    f"https://api.github.com/repos/{repo}/check-runs/{run_id}/annotations",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    timeout=10,
                )
                if r.status_code == 200:
                    for ann in r.json()[:8]:
                        path = ann.get("path", "")
                        line = ann.get("start_line", "")
                        msg = (ann.get("message") or "").strip()
                        ann_str = f"  {path}:{line}: {msg}"[:200]
                        parts.append(ann_str)
                        chars_used += len(ann_str)
                        if chars_used >= max_excerpt_chars:
                            break
            except Exception:
                pass  # degrade gracefully — annotations are best-effort

    evidence["log_excerpt"] = "\n".join(parts)
    return evidence


def fetch_merge_conflict_evidence(
    repo_path: str,
    max_excerpt_chars: int = 3000,
) -> dict:
    """Build a merge conflict evidence dict from local git state.

    Runs git commands against repo_path to discover which files are conflicted
    and extracts the conflict diff vs origin/main.  Degrades gracefully when
    git is unavailable or the working tree is clean.
    """
    conflicted_files: list = []
    diff_excerpt = ""

    try:
        status_out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            stderr=subprocess.DEVNULL,
            timeout=15,
        ).decode(errors="replace")
        conflicted_files = [
            line[3:].strip()
            for line in status_out.splitlines()
            if line[:2] in ("UU", "AA", "DD", "AU", "UA", "DU", "UD")
        ]
    except Exception:
        pass

    try:
        diff_out = subprocess.check_output(
            ["git", "diff", "origin/main...HEAD"],
            cwd=repo_path,
            stderr=subprocess.DEVNULL,
            timeout=15,
        ).decode(errors="replace")
        diff_excerpt = diff_out[:max_excerpt_chars]
        if len(diff_out) > max_excerpt_chars:
            diff_excerpt += "\n... (truncated)"
    except Exception:
        pass

    return {
        "conflicted_files": conflicted_files,
        "diff_excerpt": diff_excerpt,
    }


# ---------------------------------------------------------------------------
# Repair prompt builders — one per deterministic failure class
# ---------------------------------------------------------------------------


def build_ci_repair_prompt(
    original_prompt: str,
    evidence: dict,
    task: dict,
    attempt: int,
    max_attempts: int,
) -> str:
    """Build a repair prompt for a CI check failure."""
    failed = ", ".join(evidence.get("failed_checks") or ["unknown"])
    excerpt = (evidence.get("log_excerpt") or "").strip()

    parts = [
        f"The task completed and local checks passed, but CI pipeline checks failed "
        f"(repair attempt {attempt} of {max_attempts}).",
        "Fix the specific CI failures listed below. Do not redo the task from scratch.",
        "",
        f"Failed CI checks: {failed}",
    ]
    if excerpt:
        parts += ["", "CI failure details:", excerpt]
    parts += ["", "--- ORIGINAL TASK ---", original_prompt]
    return "\n".join(parts)


def build_merge_conflict_repair_prompt(
    original_prompt: str,
    evidence: dict,
    task: dict,
    attempt: int,
    max_attempts: int,
) -> str:
    """Build a repair prompt for a merge conflict."""
    files = ", ".join(evidence.get("conflicted_files") or ["unknown"])
    excerpt = (evidence.get("diff_excerpt") or "").strip()

    parts = [
        f"The task completed but the pull request could not be merged due to conflicts "
        f"(repair attempt {attempt} of {max_attempts}).",
        "Sync with the main branch and resolve the conflicts. Do not redo the task from scratch.",
        "",
        f"Conflicted with main branch. Affected files: {files}",
    ]
    if excerpt:
        parts += ["", "Diff vs main (excerpt):", excerpt[:3000]]
    parts += [
        "",
        "Steps: git fetch origin, rebase onto main (or resolve conflicts), re-run checks.",
        "",
        "--- ORIGINAL TASK ---",
        original_prompt,
    ]
    return "\n".join(parts)


def build_completion_evidence_repair_prompt(
    original_prompt: str,
    evidence: dict,
    task: dict,
    attempt: int,
    max_attempts: int,
) -> str:
    """Build a repair prompt for a completion evidence block."""
    reasons = "; ".join(evidence.get("reasons") or ["no evidence recorded"])

    parts = [
        f"The task worker exited successfully but the completion evidence gate rejected the result "
        f"(repair attempt {attempt} of {max_attempts}).",
        "Perform the missing work that the gate could not find evidence of. Do not redo the task from scratch.",
        "",
        f"Gate rejection reasons: {reasons}",
        "",
        "--- ORIGINAL TASK ---",
        original_prompt,
    ]
    return "\n".join(parts)


def build_gate_block_repair_prompt(
    original_prompt: str,
    evidence: dict,
    task: dict,
    attempt: int,
    max_attempts: int,
) -> str:
    """Build a repair prompt for a gate block."""
    gate = evidence.get("gate", "unknown")
    reasons = "; ".join(evidence.get("reasons") or ["no reasons given"])
    authority = evidence.get("authority", "")

    parts = [
        f"The task was blocked by the '{gate}' gate "
        f"(repair attempt {attempt} of {max_attempts}).",
        "Address the issues the gate identified. Do not redo the task from scratch.",
        "",
        f"Gate: {gate}",
    ]
    if authority:
        parts.append(f"Authority: {authority}")
    parts += [f"Issues: {reasons}", "", "--- ORIGINAL TASK ---", original_prompt]
    return "\n".join(parts)


def build_deterministic_repair_prompt(
    failure_class: str,
    original_prompt: str,
    evidence: dict,
    task: dict,
    attempt: int,
    max_attempts: int,
) -> str:
    """Dispatch to the appropriate repair prompt builder for a failure class."""
    if failure_class == CI_CHECK_FAILURE:
        return build_ci_repair_prompt(original_prompt, evidence, task, attempt, max_attempts)
    if failure_class == MERGE_CONFLICT:
        return build_merge_conflict_repair_prompt(original_prompt, evidence, task, attempt, max_attempts)
    if failure_class == COMPLETION_EVIDENCE_BLOCK:
        return build_completion_evidence_repair_prompt(original_prompt, evidence, task, attempt, max_attempts)
    if failure_class == GATE_BLOCK:
        return build_gate_block_repair_prompt(original_prompt, evidence, task, attempt, max_attempts)
    return original_prompt
