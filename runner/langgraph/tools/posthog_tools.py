"""PostHog reader tools — query event counts and funnels via the PostHog Query API.

Degrades gracefully when ``POSTHOG_PERSONAL_API_KEY`` / ``POSTHOG_PROJECT_ID``
are absent: every entry point returns an ``{"available": False, ...}`` result
instead of raising, so callers (e.g. the launch readiness scorecard) can check
analytics health without the runner crashing when credentials aren't configured.
"""
import requests

from config import get_config
from tools.http_retry import retry_request
from tools.log_tools import log_event

_TIMEOUT = 15


def _headers():
    cfg = get_config()
    return {
        "Authorization": f"Bearer {cfg.posthog_personal_api_key}",
        "Content-Type": "application/json",
    }


def _query_url():
    cfg = get_config()
    return f"{cfg.posthog_host}/api/projects/{cfg.posthog_project_id}/query/"


def _escape_hogql_string(value: str) -> str:
    """Escape a value for safe interpolation into a HogQL single-quoted string literal."""
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def _run_query(query: dict, *, action: str) -> dict:
    """POST a query payload to the PostHog query API; returns the parsed response or an error result."""
    cfg = get_config()
    if not cfg.has_posthog:
        log_event("posthog_degraded", {"reason": "no POSTHOG_PERSONAL_API_KEY/POSTHOG_PROJECT_ID", "action": action})
        return {"available": False, "reason": "no POSTHOG_PERSONAL_API_KEY/POSTHOG_PROJECT_ID"}
    try:
        r = retry_request(
            requests.post,
            _query_url(),
            headers=_headers(),
            json={"query": query},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return {"available": True, "response": r.json()}
    except Exception as e:
        log_event("error", {"tool": "posthog", "action": action, "error": str(e)})
        return {"available": False, "error": str(e)}


def query_event_count(event: str, days: int = 7) -> dict:
    """Count occurrences of ``event`` over the trailing ``days`` days.

    Returns::

        {"available": True, "event": str, "days": int, "count": int}
        {"available": False, "reason"|"error": str}
    """
    hogql = (
        f"SELECT count() FROM events WHERE event = '{_escape_hogql_string(event)}' "
        f"AND timestamp >= now() - INTERVAL {int(days)} DAY"
    )
    result = _run_query({"kind": "HogQLQuery", "query": hogql}, action="query_event_count")
    if not result.get("available"):
        return result

    try:
        rows = result["response"].get("results") or []
        count = int(rows[0][0]) if rows and rows[0] else 0
    except (KeyError, IndexError, TypeError, ValueError) as e:
        log_event("error", {"tool": "posthog", "action": "query_event_count", "error": f"unexpected response shape: {e}"})
        return {"available": False, "error": f"unexpected response shape: {e}"}

    return {"available": True, "event": event, "days": days, "count": count}


def query_funnel(events: list, days: int = 7) -> dict:
    """Run a funnel over an ordered list of event names for the trailing ``days`` days.

    Returns::

        {"available": True, "events": [...], "days": int, "steps": [{"name": str, "count": int}, ...]}
        {"available": False, "reason"|"error": str}
    """
    if not events:
        return {"available": False, "error": "no events provided"}

    query = {
        "kind": "FunnelsQuery",
        "series": [{"kind": "EventsNode", "event": e, "name": e} for e in events],
        "dateRange": {"date_from": f"-{int(days)}d"},
    }
    result = _run_query(query, action="query_funnel")
    if not result.get("available"):
        return result

    try:
        raw_steps = result["response"].get("results") or []
        # PostHog nests funnel steps in an extra list when the query is
        # broken down (e.g. by a property); unwrap the common case where the
        # first entry is itself a list of step dicts.
        if raw_steps and isinstance(raw_steps[0], list):
            raw_steps = raw_steps[0]
        steps = [
            {"name": step.get("name"), "count": int(step.get("count", 0))}
            for step in raw_steps
        ]
    except (KeyError, TypeError, ValueError) as e:
        log_event("error", {"tool": "posthog", "action": "query_funnel", "error": f"unexpected response shape: {e}"})
        return {"available": False, "error": f"unexpected response shape: {e}"}

    return {"available": True, "events": events, "days": days, "steps": steps}


def format_analytics_summary(event_counts: dict = None, funnels: dict = None) -> str:
    """Format ``query_event_count``/``query_funnel`` results into a human-readable block.

    ``event_counts`` maps a label to a ``query_event_count`` result dict.
    ``funnels`` maps a label to a ``query_funnel`` result dict.
    Pure function — no I/O, safe to unit test directly.
    """
    event_counts = event_counts or {}
    funnels = funnels or {}
    lines = []

    for label, result in event_counts.items():
        if result.get("available"):
            lines.append(f"{label}: {result.get('count')} events over {result.get('days')}d")
        else:
            reason = result.get("error") or result.get("reason") or "unavailable"
            lines.append(f"{label}: unavailable ({reason})")

    for label, result in funnels.items():
        if not result.get("available"):
            reason = result.get("error") or result.get("reason") or "unavailable"
            lines.append(f"{label}: unavailable ({reason})")
            continue
        steps = result.get("steps") or []
        if not steps:
            lines.append(f"{label}: no steps returned")
            continue
        first_count = steps[0].get("count") or 0
        parts = []
        for step in steps:
            count = step.get("count") or 0
            rate = f" ({count / first_count:.0%})" if first_count else ""
            parts.append(f"{step.get('name')}={count}{rate}")
        lines.append(f"{label}: " + " -> ".join(parts))

    if not lines:
        return "No analytics data requested."
    return "\n".join(lines)
