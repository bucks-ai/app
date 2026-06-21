"""Auto-Repair Loop v2.

When check.sh fails after a successful worker run, re-dispatch the same worker
with the check failure output so it can fix the issues in place.  The loop runs
up to MAX_AUTO_REPAIR_ATTEMPTS times before giving up and letting the normal
failure guard handle the task.

Gate behaviour (controlled via config.py / env vars):
- AUTO_REPAIR_LOOP_ENABLED=true  (default): auto-repair is active.
- MAX_AUTO_REPAIR_ATTEMPTS=2     (default): maximum repair attempts per task.
"""


def should_auto_repair(
    worker_result: dict,
    check_passed: "bool | None",
    auto_repair_attempt: int,
    max_attempts: int,
) -> bool:
    """True when conditions are met for a repair attempt.

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
