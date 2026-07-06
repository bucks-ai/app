"""Pure mapping logic for Slack interactive approvals.

Bridges the runner's existing file-based approval gates (merge approval,
SQL approval, resource/credential request, strategic review — see
``risk_based_merge_approval.py``, ``sql_environment_gate.py``,
``resource_gate.py``, ``strategic_decision_gate.py`` and their call sites in
``graph.py``) to Slack Block Kit messages with Approve/Reject buttons.

This module does no network I/O and touches no disk — it only maps:

    outbox filename            -> request_type / request_id / inbox filename
    request                    -> Slack Block Kit message
    button click payload       -> inbox_filename + content to write (or not)

``approvals_daemon.py`` is the thin, side-effecting driver around these pure
functions: it polls ``outbox/``, calls ``build_approval_blocks`` to post, and
on a button click calls ``parse_button_value`` + ``resolve_action`` to decide
what (if anything) to write into ``inbox/``.

Every approval type here mirrors the *exact* inbox convention the graph
already expects — this module changes nothing about the graph side:

  - merge_approval:   inbox/{task_id}_merge_approved.txt        (existence-only; no reject file convention)
  - sql_approval:     inbox/{task_id}_sql_approved.txt          (content read: "rejected"/"reject"/"no" -> rejected, else approved)
  - resource_request: inbox/{task_id}_resources_provided.txt    (existence-only; contents never read by the graph)
  - strategic_review: inbox/strategic_review_{loop}_approved.txt (existence-only; no reject file convention)

For the three existence-only types, "Reject" cannot be expressed as a file —
the graph's own documented reject path is "do not create the file". So a
Reject click for those types deliberately writes nothing; only sql_approval
has a real reject-by-content mechanism.
"""
import json
import re
from typing import Optional

APPROVAL_TYPES = ("merge_approval", "sql_approval", "resource_request", "strategic_review")

MAX_EXCERPT_CHARS = 1500

_DISPLAY_TITLES = {
    "merge_approval": "Merge Approval Required",
    "sql_approval": "SQL Approval Required",
    "resource_request": "Resource / Credential Request",
    "strategic_review": "Strategic Review Checkpoint",
}

_MERGE_RE = re.compile(r"^(?P<request_id>.+)_merge_approval_request\.txt$")
_SQL_RE = re.compile(r"^(?P<request_id>.+)_sql_approval\.sql$")
_RESOURCE_RE = re.compile(r"^(?P<request_id>.+)_resource_request\.txt$")
_STRATEGIC_RE = re.compile(r"^strategic_review_(?P<request_id>\d+)\.txt$")

# Defensive redaction for anything that looks like a secret, in case an outbox
# file ever contains one (it shouldn't — see resource_gate.py/sql_guard.py —
# but Slack messages are a one-way door once posted, so redact belt-and-braces).
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://\S+"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{10,}|xox[baprs]-[A-Za-z0-9-]{10,}|ghp_[A-Za-z0-9]{10,})\b"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*\S+"),
)


def classify_outbox_file(filename: str) -> Optional[dict]:
    """Classify an ``outbox/`` filename as an approval request, or ``None``.

    Many files in ``outbox/`` are plain prompts/reports, not approval
    requests — those must return ``None`` so the daemon leaves them alone.
    """
    m = _SQL_RE.match(filename)
    if m:
        request_id = m.group("request_id")
        return {
            "request_type": "sql_approval",
            "request_id": request_id,
            "inbox_filename": inbox_filename_for("sql_approval", request_id),
            "supports_reject_file": True,
        }
    m = _MERGE_RE.match(filename)
    if m:
        request_id = m.group("request_id")
        return {
            "request_type": "merge_approval",
            "request_id": request_id,
            "inbox_filename": inbox_filename_for("merge_approval", request_id),
            "supports_reject_file": False,
        }
    m = _RESOURCE_RE.match(filename)
    if m:
        request_id = m.group("request_id")
        return {
            "request_type": "resource_request",
            "request_id": request_id,
            "inbox_filename": inbox_filename_for("resource_request", request_id),
            "supports_reject_file": False,
        }
    m = _STRATEGIC_RE.match(filename)
    if m:
        request_id = m.group("request_id")
        return {
            "request_type": "strategic_review",
            "request_id": request_id,
            "inbox_filename": inbox_filename_for("strategic_review", request_id),
            "supports_reject_file": False,
        }
    return None


def inbox_filename_for(request_type: str, request_id: str) -> str:
    """The exact inbox/ fulfillment filename the graph polls for, per type."""
    if request_type == "merge_approval":
        return f"{request_id}_merge_approved.txt"
    if request_type == "sql_approval":
        return f"{request_id}_sql_approved.txt"
    if request_type == "resource_request":
        return f"{request_id}_resources_provided.txt"
    if request_type == "strategic_review":
        return f"strategic_review_{request_id}_approved.txt"
    raise ValueError(f"unknown request_type: {request_type!r}")


def supports_reject_file(request_type: str) -> bool:
    """True only for sql_approval — the one type the graph reads content from."""
    if request_type not in APPROVAL_TYPES:
        raise ValueError(f"unknown request_type: {request_type!r}")
    return request_type == "sql_approval"


def sanitize_excerpt(text: str) -> str:
    """Redact anything that looks like a secret/connection-string/credential."""
    if not text:
        return ""
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def truncate(text: str, limit: int = MAX_EXCERPT_CHARS) -> str:
    if not text:
        return ""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n… (truncated)"


def build_approval_blocks(request_type: str, request_id: str, source_label: str, body: str) -> list:
    """Build the Block Kit message posted when a new approval request appears.

    ``source_label`` is the outbox filename (shown for traceability);
    ``body`` is the raw file content, sanitized and truncated here.
    """
    if request_type not in APPROVAL_TYPES:
        raise ValueError(f"unknown request_type: {request_type!r}")

    title = _DISPLAY_TITLES.get(request_type, request_type)
    excerpt = truncate(sanitize_excerpt(body))
    reject_note = (
        "" if supports_reject_file(request_type) else
        "\n_Reject leaves the runner blocked — this request type has no reject-file convention._"
    )

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f":rotating_light: {title}", "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Type:* `{request_type}`\n*Request ID:* `{request_id}`\n*Source:* `{source_label}`{reject_note}",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"```{excerpt}```" if excerpt else "_(empty request file)_"},
        },
        {
            "type": "actions",
            "block_id": "runner_approval_actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "runner_approve",
                    "value": json.dumps({"request_type": request_type, "request_id": request_id}),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "runner_reject",
                    "value": json.dumps({"request_type": request_type, "request_id": request_id}),
                },
            ],
        },
    ]
    return blocks


def build_result_blocks(request_type: str, request_id: str, outcome: str, actor: str) -> list:
    """Build the Block Kit message the daemon updates the original post with."""
    title = _DISPLAY_TITLES.get(request_type, request_type)
    emoji = {"approved": ":white_check_mark:", "rejected": ":x:", "rejected_no_file": ":x:"}.get(outcome, ":grey_question:")
    label = {"approved": "Approved", "rejected": "Rejected", "rejected_no_file": "Rejected"}.get(outcome, outcome)
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{title} — {label}", "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{label}* by *{actor}*\n*Type:* `{request_type}`  ·  *Request ID:* `{request_id}`",
            },
        },
    ]


def resolve_action(request_type: str, request_id: str, action: str) -> dict:
    """Decide what a button click means for the inbox side. Pure, no I/O.

    Returns ``{"should_write": bool, "inbox_filename": str, "content": str|None, "outcome": str}``.
    ``outcome`` is one of ``"approved"``, ``"rejected"`` (a reject file was
    written — sql_approval only), or ``"rejected_no_file"`` (no reject-file
    convention exists for this type, so nothing is written; the request stays
    blocked until a human resolves it another way).
    """
    if request_type not in APPROVAL_TYPES:
        raise ValueError(f"unknown request_type: {request_type!r}")
    if action not in ("approve", "reject"):
        raise ValueError(f"unknown action: {action!r}")

    inbox_filename = inbox_filename_for(request_type, request_id)

    if action == "approve":
        return {"should_write": True, "inbox_filename": inbox_filename, "content": "approved\n", "outcome": "approved"}

    if supports_reject_file(request_type):
        return {"should_write": True, "inbox_filename": inbox_filename, "content": "rejected\n", "outcome": "rejected"}

    return {"should_write": False, "inbox_filename": inbox_filename, "content": None, "outcome": "rejected_no_file"}


def parse_button_value(raw_value) -> dict:
    """Parse and validate a Slack button's ``value`` payload.

    Raises ``ValueError`` on anything malformed — missing/invalid JSON, wrong
    shape, unknown request_type, or missing request_id. Callers must catch
    this and refuse to act rather than guess at the request's identity.
    """
    try:
        data = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"malformed button payload: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("button payload is not a JSON object")

    request_type = data.get("request_type")
    request_id = data.get("request_id")

    if request_type not in APPROVAL_TYPES:
        raise ValueError(f"unknown request_type in payload: {request_type!r}")
    if not request_id or not isinstance(request_id, str):
        raise ValueError(f"missing or invalid request_id in payload: {request_id!r}")

    return {"request_type": request_type, "request_id": request_id}
