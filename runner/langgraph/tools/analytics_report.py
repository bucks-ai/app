"""Weekly analytics report — composes the PostHog funnel reader and the
Sentry issue reader into a single human-readable weekly digest.

Written to outbox/analytics_report.txt and logged as ``analytics_report_ready``.
Exposed as the ``python main.py analytics-report`` CLI command.

Each section degrades independently: a missing PostHog or Sentry integration
renders "not configured" for that section only, never raises, and never
blocks the other section from rendering.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config import get_config
from tools.log_tools import log_event
from tools.posthog_tools import query_funnel
from tools.sentry_tools import list_new_issues

_RUNNER_DIR = Path(__file__).parent.parent

# Canonical signup -> deploy funnel, in order. Source of truth for the event
# names/order is src/lib/analytics/events.ts (ANALYTICS_EVENTS); mirrored here
# because the runner has no dependency on the Next.js app's TS sources.
CANONICAL_FUNNEL_EVENTS = [
    "user_signed_up",
    "intake_started",
    "intake_submitted",
    "blueprint_generated",
    "blueprint_saved",
    "tool_approval_requested",
    "tool_approved",
    "repo_created",
    "scaffold_prepared",
    "vercel_project_created",
    "deploy_succeeded",
]

_MAX_SENTRY_ISSUE_LINES = 10


def _step_count(steps: list[dict], name: str) -> Optional[int]:
    """Return the funnel step count for ``name``, or None if the step is absent."""
    for step in steps:
        if step.get("name") == name:
            return step.get("count")
    return None


def format_funnel_lines(funnel_result: dict) -> list[str]:
    """Render funnel step counts as indented lines. Pure — no I/O."""
    if not funnel_result.get("available"):
        reason = funnel_result.get("error") or funnel_result.get("reason") or "not configured"
        return [f"  not configured ({reason})"]
    steps = funnel_result.get("steps") or []
    if not steps:
        return ["  no funnel data returned"]
    first_count = steps[0].get("count") or 0
    lines = []
    for step in steps:
        count = step.get("count") or 0
        rate = f" ({count / first_count:.0%})" if first_count else ""
        lines.append(f"  {step.get('name')}: {count}{rate}")
    return lines


def format_sentry_lines(sentry_available: bool, issues: list[dict]) -> list[str]:
    """Render new-Sentry-issue lines. Pure — no I/O."""
    if not sentry_available:
        return ["  not configured (missing SENTRY_AUTH_TOKEN/SENTRY_ORG/SENTRY_PROJECT)"]
    if not issues:
        return ["  no new issues"]
    lines = []
    for issue in issues[:_MAX_SENTRY_ISSUE_LINES]:
        short_id = issue.get("short_id") or issue.get("id") or "?"
        lines.append(
            f"  [{short_id}] {issue.get('title')} "
            f"(count={issue.get('count', 0)}, users={issue.get('user_count', 0)})"
        )
    if len(issues) > _MAX_SENTRY_ISSUE_LINES:
        lines.append(f"  ... and {len(issues) - _MAX_SENTRY_ISSUE_LINES} more")
    return lines


def build_report(
    *,
    funnel_result: dict,
    sentry_available: bool,
    sentry_issues: list[dict] = None,
    days: int = 7,
    generated_at: str = None,
) -> dict:
    """Build the weekly analytics report text from already-fetched data. Pure — no I/O.

    Returns a dict with:
        text                  — the full report text
        headline              — the single labeled line answering "how many
                                 users reached a deployed repo this week"
        repo_created_count    — unique users reaching repo_created, or None
        deploy_succeeded_count— unique users reaching deploy_succeeded, or None
        sentry_new_issue_count— count of new Sentry issues, or None when
                                 Sentry isn't configured
    """
    sentry_issues = sentry_issues or []
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()

    funnel_available = funnel_result.get("available", False)
    steps = funnel_result.get("steps") or [] if funnel_available else []
    repo_created_count = _step_count(steps, "repo_created")
    deploy_succeeded_count = _step_count(steps, "deploy_succeeded")

    if funnel_available:
        headline = (
            f"Users who reached a deployed repo this week: "
            f"{deploy_succeeded_count if deploy_succeeded_count is not None else 0}"
        )
    else:
        reason = funnel_result.get("error") or funnel_result.get("reason") or "not configured"
        headline = f"Users who reached a deployed repo this week: not configured ({reason})"

    lines = [
        "=" * 60,
        "Weekly Analytics Report",
        "=" * 60,
        f"  Generated : {generated_at}",
        f"  Window    : trailing {days}d",
        "",
        headline,
        "",
        f"Signup -> Deploy Funnel ({days}d)",
        "-" * 40,
    ]
    lines.extend(format_funnel_lines(funnel_result))
    lines.append("")
    lines.append(
        f"  Unique users reaching repo_created     : "
        f"{repo_created_count if repo_created_count is not None else 'not configured'}"
    )
    lines.append(
        f"  Unique users reaching deploy_succeeded : "
        f"{deploy_succeeded_count if deploy_succeeded_count is not None else 'not configured'}"
    )
    lines.append("")
    lines.append(f"New Sentry Issues (last {days}d)")
    lines.append("-" * 40)
    lines.extend(format_sentry_lines(sentry_available, sentry_issues))
    lines.append("")
    lines.append("=" * 60)
    lines.append("")

    return {
        "text": "\n".join(lines),
        "headline": headline,
        "repo_created_count": repo_created_count,
        "deploy_succeeded_count": deploy_succeeded_count,
        "sentry_new_issue_count": len(sentry_issues) if sentry_available else None,
    }


def generate_analytics_report(days: int = 7) -> dict:
    """Fetch live PostHog/Sentry data, build the report, write it to outbox/,
    and log ``analytics_report_ready``. Never raises — each data source
    degrades independently via its own reader tool.
    """
    cfg = get_config()

    funnel_result = query_funnel(list(CANONICAL_FUNNEL_EVENTS), days=days)

    since_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    sentry_issues = list_new_issues(since_iso)

    result = build_report(
        funnel_result=funnel_result,
        sentry_available=cfg.has_sentry,
        sentry_issues=sentry_issues,
        days=days,
    )

    report_path = _RUNNER_DIR / "outbox" / "analytics_report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(result["text"])

    log_event("analytics_report_ready", {
        "days": days,
        "repo_created_count": result["repo_created_count"],
        "deploy_succeeded_count": result["deploy_succeeded_count"],
        "sentry_new_issue_count": result["sentry_new_issue_count"],
        "funnel_available": funnel_result.get("available", False),
        "sentry_available": cfg.has_sentry,
    })

    return {
        "report_path": str(report_path),
        **result,
    }
