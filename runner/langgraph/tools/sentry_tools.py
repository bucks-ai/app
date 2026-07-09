"""Sentry REST API reader tools — degrades gracefully without credentials.

Read-only: lists issues newly seen since a given timestamp and builds a short
project issue summary. Plain ``requests`` calls through ``tools/http_retry``;
no Sentry SDK dependency.
"""
from datetime import datetime, timezone

import requests

from config import get_config
from tools.http_retry import retry_request
from tools.log_tools import log_event

_API_BASE = "https://sentry.io/api/0"


def _headers() -> dict:
    cfg = get_config()
    return {"Authorization": f"Bearer {cfg.sentry_auth_token}"}


def _issues_url() -> str:
    cfg = get_config()
    return f"{_API_BASE}/projects/{cfg.sentry_org}/{cfg.sentry_project}/issues/"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_issue(raw: dict) -> dict:
    """Normalize one raw Sentry issue payload into the flat shape the runner
    logs and summarizes, decoupling callers from Sentry's nested API shape."""
    metadata = raw.get("metadata") or {}
    return {
        "id": raw.get("id"),
        "short_id": raw.get("shortId"),
        "title": raw.get("title") or metadata.get("type") or "unknown",
        "culprit": raw.get("culprit"),
        "level": raw.get("level"),
        "status": raw.get("status"),
        "count": int(raw.get("count") or 0),
        "user_count": int(raw.get("userCount") or 0),
        "first_seen": raw.get("firstSeen"),
        "last_seen": raw.get("lastSeen"),
        "permalink": raw.get("permalink"),
    }


def filter_issues_since(issues: list[dict], since_iso: str) -> list[dict]:
    """Keep only parsed issues first seen at/after ``since_iso``.

    Sentry's ``start``/``end`` query params scope the search window server
    side, but this local filter is the source of truth for "new" so a caller
    doesn't have to trust that Sentry applied the window as expected.
    """
    if not since_iso:
        return list(issues)
    since = _parse_iso(since_iso)
    if since is None:
        return list(issues)
    kept = []
    for issue in issues:
        first_seen = _parse_iso(issue.get("first_seen"))
        if first_seen is None or first_seen >= since:
            kept.append(issue)
    return kept


def _parse_iso(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def summarize_issues(issues: list[dict]) -> dict:
    """Aggregate parsed issues into counts by level plus the top issues by
    event count. Pure — no network, no Sentry-specific field names leak out."""
    by_level: dict = {}
    for issue in issues:
        level = issue.get("level") or "unknown"
        by_level[level] = by_level.get(level, 0) + 1
    top = sorted(issues, key=lambda i: i.get("count") or 0, reverse=True)[:5]
    return {
        "total": len(issues),
        "by_level": by_level,
        "total_events": sum(i.get("count") or 0 for i in issues),
        "total_users_affected": sum(i.get("user_count") or 0 for i in issues),
        "top_issues": top,
    }


def format_issue_summary(summary: dict) -> str:
    """Build a human-readable summary string from ``summarize_issues`` output."""
    if summary["total"] == 0:
        return "Sentry: no unresolved issues."
    lines = [
        f"Sentry: {summary['total']} unresolved issue(s), "
        f"{summary['total_events']} event(s), "
        f"{summary['total_users_affected']} user(s) affected."
    ]
    if summary["by_level"]:
        levels = ", ".join(f"{level}={count}" for level, count in sorted(summary["by_level"].items()))
        lines.append(f"  By level: {levels}")
    for issue in summary["top_issues"]:
        short_id = issue.get("short_id") or issue.get("id") or "?"
        lines.append(f"  [{short_id}] {issue.get('title')} (count={issue.get('count')})")
    return "\n".join(lines)


def list_new_issues(since_iso: str) -> list[dict]:
    """List unresolved issues first seen at/after ``since_iso`` (ISO 8601).

    Degrades to an empty list without SENTRY_AUTH_TOKEN / SENTRY_ORG /
    SENTRY_PROJECT — never raises, so callers can use it unconditionally.
    """
    cfg = get_config()
    if not cfg.has_sentry:
        log_event("sentry_degraded", {"reason": "no Sentry credentials", "action": "list_new_issues"})
        return []
    try:
        r = retry_request(
            requests.get,
            _issues_url(),
            headers=_headers(),
            params={
                "query": "is:unresolved",
                "sort": "new",
                "start": since_iso,
                "end": _now_iso(),
            },
            timeout=15,
        )
        r.raise_for_status()
        issues = [parse_issue(raw) for raw in r.json()]
        return filter_issues_since(issues, since_iso)
    except Exception as e:
        log_event("error", {"tool": "sentry", "action": "list_new_issues", "error": str(e)})
        return []


def issue_summary() -> str:
    """Fetch current unresolved project issues and return a formatted summary.

    Degrades to a plain no-op message without SENTRY_AUTH_TOKEN / SENTRY_ORG /
    SENTRY_PROJECT — never raises.
    """
    cfg = get_config()
    if not cfg.has_sentry:
        log_event("sentry_degraded", {"reason": "no Sentry credentials", "action": "issue_summary"})
        return "Sentry: not configured (missing SENTRY_AUTH_TOKEN/SENTRY_ORG/SENTRY_PROJECT)."
    try:
        r = retry_request(
            requests.get,
            _issues_url(),
            headers=_headers(),
            params={"query": "is:unresolved", "sort": "freq"},
            timeout=15,
        )
        r.raise_for_status()
        issues = [parse_issue(raw) for raw in r.json()]
        return format_issue_summary(summarize_issues(issues))
    except Exception as e:
        log_event("error", {"tool": "sentry", "action": "issue_summary", "error": str(e)})
        return "Sentry: error fetching issue summary."
