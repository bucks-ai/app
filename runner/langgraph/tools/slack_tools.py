"""Slack notification tools — pushes notable runner events to a Slack webhook.

Degrades gracefully when ``SLACK_WEBHOOK_URL`` is absent: every entry point
becomes a no-op and nothing is posted. Reaching Slack failing (network error,
non-2xx response) never interrupts the runner — the failure is swallowed and
recorded as a ``slack_degraded`` event so the flight recorder keeps the trail.

The notification sink hangs off the flight recorder: ``log_tools.log_event``
calls :func:`notify_event` for every event it records, and this module decides
(via ``cfg.slack_notify_events``) which ones are worth a Slack ping. Keeping the
filter here — rather than sprinkling notify calls across graph nodes — means
notifications stay in sync with the event stream automatically.
"""
import requests

from config import get_config
from tools.log_tools import log_event

_TIMEOUT = 10

# Emoji prefixes per event for quick visual scanning in a Slack channel.
_EVENT_EMOJI = {
    "task_completed": ":white_check_mark:",
    "error": ":x:",
    "loop_stopped": ":octagonal_sign:",
    "loop_blocked_on_deploy": ":no_entry:",
    "deploy_poll_failed": ":rotating_light:",
    "deploy_poll_timeout": ":hourglass:",
    "sql_scan_blocked": ":shield:",
    "sql_approval_pending": ":hourglass_flowing_sand:",
    "check_failed": ":warning:",
}


def _detail_for(event_type: str, payload: dict) -> str:
    """Build a one-line human-readable detail string for a notable event.

    Pulls the most salient fields per event type; falls back to a compact
    key=value rendering of the payload for anything unrecognized.
    """
    p = payload or {}

    if event_type == "error":
        return str(p.get("error") or "")
    if event_type == "loop_stopped":
        return f"reason: {p.get('reason', 'unknown')}"
    if event_type == "loop_blocked_on_deploy":
        bits = [f"reason: {p.get('reason', 'unknown')}"]
        if p.get("state"):
            bits.append(f"state: {p['state']}")
        return "  ".join(bits)
    if event_type in ("deploy_poll_failed", "deploy_poll_timeout"):
        bits = []
        if p.get("state"):
            bits.append(f"state: {p['state']}")
        if p.get("polls") is not None:
            bits.append(f"polls: {p['polls']}")
        if p.get("elapsed") is not None:
            bits.append(f"elapsed: {p['elapsed']}s")
        return "  ".join(bits)
    if event_type == "sql_scan_blocked":
        scan = p.get("scan") or {}
        blocked = scan.get("blocked_terms") or []
        return f"blocked terms: {', '.join(blocked)}" if blocked else "SQL scan blocked"
    if event_type == "sql_approval_pending":
        return str(p.get("message") or p.get("review_path") or "SQL awaiting approval")
    if event_type == "check_failed":
        return str(p.get("error") or "checks failed")

    # Generic fallback: a few payload keys, compactly rendered.
    interesting = {k: v for k, v in p.items() if not isinstance(v, (dict, list))}
    if not interesting:
        return ""
    shown = list(interesting.items())[:4]
    return "  ".join(f"{k}: {v}" for k, v in shown)


def format_event(event_type: str, payload: dict = None, task_id: str = None) -> str:
    """Render a runner event as Slack message text (pure / side-effect free)."""
    emoji = _EVENT_EMOJI.get(event_type, ":robot_face:")
    head = f"{emoji} *{event_type}*"
    if task_id:
        head += f"  ·  task `{task_id}`"
    detail = _detail_for(event_type, payload or {})
    return f"{head}\n{detail}" if detail else head


def post_message(text: str, blocks: list = None) -> dict:
    """Post a message to the configured Slack Incoming Webhook.

    Returns ``{"available": False, ...}`` when no webhook is configured, and
    ``{"available": True, "ok": bool, ...}`` otherwise. Network/HTTP failures
    are caught and reported as ``ok: False`` (never raised).
    """
    cfg = get_config()
    if not cfg.has_slack:
        return {"available": False, "reason": "no SLACK_WEBHOOK_URL"}

    payload = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        r = requests.post(cfg.slack_webhook_url, json=payload, timeout=_TIMEOUT)
        r.raise_for_status()
        return {"available": True, "ok": True, "status_code": r.status_code}
    except Exception as e:
        # Recorded as a non-notable event so this never loops back into Slack.
        log_event("slack_degraded", {"action": "post_message", "error": str(e)})
        return {"available": True, "ok": False, "error": str(e)}


def notify_event(event_type: str, payload: dict = None, task_id: str = None) -> dict:
    """Post a Slack notification for ``event_type`` when it is in the notify set.

    Cheap no-op when notifications are disabled, no webhook is configured, or the
    event isn't one of ``cfg.slack_notify_events`` — so it's safe to call for
    every flight-recorder event.
    """
    cfg = get_config()
    if not cfg.slack_notify or not cfg.has_slack:
        return {"available": False, "reason": "slack notifications disabled"}
    if event_type not in cfg.slack_notify_events:
        return {"available": True, "ok": False, "skipped": True, "reason": "event not notable"}
    return post_message(format_event(event_type, payload, task_id))
