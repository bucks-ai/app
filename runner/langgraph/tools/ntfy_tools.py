"""Phone push via ntfy.sh — exactly ONE alert class reaches the founder phone.

Only credential/account-request events are pushed to the phone (per the M4c
phone-push doctrine: the phone buzzes zero times on a quiet night unless a
human genuinely must create an account). Everything else is the babysitter's
job and stays in Slack.

ntfy.sh is used because Slack only notifies with the app open; credential
requests sat unseen for hours during M4b because of exactly this gap.

Three-place rule: NTFY_TOPIC appears in config.py (field), README.md (env
table), and tests/test_ntfy_tools.py. Do not add the variable anywhere else.
"""
import os

import requests

# Events that cross the phone boundary. This set is intentionally tiny.
# Every addition is a regression: more buzzes means the ones that matter get
# ignored, which defeats the purpose.
PHONE_PUSH_EVENTS = frozenset({
    "resource_request_pending",
    "dependency_batch_request",
})

_TIMEOUT = 8


def _topic() -> str:
    """Return the configured ntfy.sh topic, or empty string when absent."""
    try:
        from config import get_config
        return getattr(get_config(), "ntfy_topic", None) or ""
    except Exception:
        return ""


def send_phone_push(title: str, message: str, *, priority: int = 4) -> dict:
    """POST a push notification to ntfy.sh/{topic}.

    Returns ``{"available": False}`` when NTFY_TOPIC is not configured.
    Network/HTTP failures are caught and recorded as ``ntfy_degraded`` — they
    never interrupt the runner or raise.

    priority: 1 (min) through 5 (urgent). 4 (high) is the right level for
    credential requests: important enough to read immediately, not so loud
    that the phone vibrates repeatedly.
    """
    topic = _topic()
    if not topic:
        return {"available": False, "reason": "no NTFY_TOPIC"}

    url = f"https://ntfy.sh/{topic}"
    headers = {
        "Title": str(title)[:250],
        "Priority": str(priority),
        "Content-Type": "text/plain",
    }
    try:
        r = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=_TIMEOUT)
        r.raise_for_status()
        return {"available": True, "ok": True, "status_code": r.status_code}
    except Exception as e:
        # Avoid circular import: log_event imports slack_tools which imports
        # config — keep this import lazy and inside the except block.
        try:
            from tools.log_tools import log_event
            log_event("ntfy_degraded", {"action": "send_phone_push", "error": str(e)})
        except Exception:
            pass
        return {"available": True, "ok": False, "error": str(e)}


def _build_push_message(event_type: str, payload: dict, task_id: str | None) -> tuple[str, str]:
    """Pure: derive (title, message) for a phone-push event."""
    p = payload or {}
    if event_type == "resource_request_pending":
        label = f" [{task_id}]" if task_id else ""
        creds = p.get("credentials") or []
        resources = p.get("resources") or []
        count = len(creds) + len(resources)
        title = f"Credential request{label}"
        lines = [f"{count} item(s) needed — check outbox."]
        if creds:
            lines.append("Credentials: " + ", ".join(str(c) for c in creds[:5]))
        if resources:
            lines.append("Resources: " + ", ".join(str(r) for r in resources[:5]))
        return title, "\n".join(lines)

    if event_type == "dependency_batch_request":
        count = p.get("count", 0)
        title = "Roadmap dependency scan"
        msg = (
            f"{count} credential(s) needed for the roadmap.\n"
            "Check outbox/dependency_batch_request.txt\n"
            "One 30-minute session provisions the whole roadmap."
        )
        return title, msg

    return event_type, str(p)[:500]


def notify_phone_event(
    event_type: str,
    payload: dict = None,
    task_id: str = None,
) -> dict:
    """Push a phone notification for events in PHONE_PUSH_EVENTS.

    Safe to call for every flight-recorder event — cheap no-op when the event
    is not in the phone-push set or NTFY_TOPIC is not configured.
    """
    if event_type not in PHONE_PUSH_EVENTS:
        return {"available": True, "ok": False, "skipped": True, "reason": "event not phone-push"}

    topic = _topic()
    if not topic:
        return {"available": False, "reason": "no NTFY_TOPIC"}

    title, message = _build_push_message(event_type, payload or {}, task_id)
    return send_phone_push(title, message)
