"""Rollback/revert policy helpers for failed deployments.

The runner should make deployment recovery explicit without silently mutating a
production branch. These helpers are pure: graph.py owns file writes and event
logging after a policy decision is made.
"""

_VALID_POLICIES = frozenset({
    "manual",
    "rollback",
    "revert",
    "rollback_then_revert",
    "disabled",
    "none",
})


def normalize_policy(policy: str | None) -> str:
    value = (policy or "manual").strip().lower().replace("-", "_")
    if value in ("off", "false"):
        return "disabled"
    if value not in _VALID_POLICIES:
        return "manual"
    return value


def deploy_failure_reason(deploy_result: dict | None) -> str | None:
    """Return the deploy failure reason that should trigger recovery policy."""
    poll = (deploy_result or {}).get("poll") or {}
    if poll.get("timed_out"):
        return "deploy_timed_out"
    if poll.get("terminal") and not poll.get("ready"):
        return "deploy_failed"
    return None


def evaluate_rollback_revert_policy(
    *,
    deploy_result: dict | None,
    policy: str | None,
    task: dict | None = None,
    commit_sha: str | None = None,
) -> dict:
    """Build a recovery decision for a failed deployment.

    Policy values:
    - manual: write a plan and require a human to choose rollback/revert
    - rollback: recommend restoring the last known-good deployment first
    - revert: recommend reverting the landed commit
    - rollback_then_revert: recommend immediate rollback, then source revert
    - disabled/none: do not create a recovery plan
    """
    normalized = normalize_policy(policy)
    reason = deploy_failure_reason(deploy_result)
    if normalized in ("disabled", "none"):
        return {
            "required": False,
            "status": "disabled",
            "policy": normalized,
            "reason": reason or "policy_disabled",
        }
    if not reason:
        return {
            "required": False,
            "status": "not_required",
            "policy": normalized,
            "reason": "no_terminal_deploy_failure",
        }

    poll = (deploy_result or {}).get("poll") or {}
    deployment = poll.get("deployment") or {}
    task = task or {}
    action = {
        "manual": "manual_review",
        "rollback": "rollback_deployment",
        "revert": "revert_commit",
        "rollback_then_revert": "rollback_deployment_then_revert_commit",
    }[normalized]

    warnings = []
    if "revert" in action and not commit_sha:
        warnings.append("No landed commit SHA was recorded; source revert must be resolved manually.")
    if "rollback" in action and not deployment:
        warnings.append("No deployment record was captured; identify the current and last known-good deployments manually.")

    return {
        "required": True,
        "status": "manual_required",
        "policy": normalized,
        "recommended_action": action,
        "reason": reason,
        "task_id": task.get("id"),
        "task_title": task.get("title"),
        "branch": task.get("branch"),
        "commit_sha": commit_sha,
        "deployment_state": poll.get("state"),
        "deployment_id": deployment.get("uid") or deployment.get("id"),
        "deployment_url": deployment.get("url"),
        "warnings": warnings,
    }


def format_recovery_plan(decision: dict) -> str:
    """Format a human-readable recovery plan for runner/outbox."""
    lines = [
        "Rollback / Revert Recovery Plan",
        "",
        f"Task: {decision.get('task_id') or 'unknown'} - {decision.get('task_title') or 'untitled'}",
        f"Failure: {decision.get('reason')}",
        f"Policy: {decision.get('policy')}",
        f"Recommended action: {decision.get('recommended_action')}",
        f"Branch: {decision.get('branch') or 'unknown'}",
        f"Commit: {decision.get('commit_sha') or 'unknown'}",
        f"Deployment state: {decision.get('deployment_state') or 'unknown'}",
        f"Deployment id: {decision.get('deployment_id') or 'unknown'}",
        f"Deployment URL: {decision.get('deployment_url') or 'unknown'}",
        "",
        "Required operator decision:",
        "1. Inspect the failed deployment logs and confirm user impact.",
        "2. If production is impaired, roll back to the last known-good deployment.",
        "3. If the landed commit is the likely cause, create a normal revert commit and run checks before pushing.",
        "4. Record the chosen action in the task or issue before resuming the runner.",
    ]
    warnings = decision.get("warnings") or []
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"
