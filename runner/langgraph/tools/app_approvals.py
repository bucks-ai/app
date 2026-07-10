"""Pure mapping logic for the in-app approval queue (mirrors tools/slack_approvals.py).

Gives the bucks.ai app the same approval power as the Slack interactive
approvals daemon, over the *same* outbox/inbox file conventions — the graph's
file-based gates (see ``risk_based_merge_approval.py``, ``sql_environment_gate.py``,
``resource_gate.py``, ``strategic_decision_gate.py`` and their call sites in
``graph.py``) are never touched by this module.

This module does no network I/O and touches no disk. It only maps:

    outbox classification (from tools.slack_approvals.classify_outbox_file)
                                -> approvals table row (for app_approvals_daemon.py to upsert)
    approvals table row (after a founder decision in the app)
                                -> inbox filename + content to write (or not)

``app_approvals_daemon.py`` is the thin, side-effecting driver around these
pure functions: it polls ``outbox/`` and calls ``classification_to_row`` to
build rows to upsert into Supabase, then polls the ``approvals`` table for
decided-but-unsynced rows and calls ``decision_to_inbox_write`` to decide what
(if anything) to write into ``inbox/``.

Decision-writing reuses ``tools.slack_approvals.resolve_action`` directly, so
the inbox-file conventions for approve/reject stay byte-for-byte identical
between the Slack daemon and the app daemon — whichever writes the inbox file
first wins (existence check before write); this module never assumes it's the
only writer.
"""
from typing import Optional

from tools.slack_approvals import (
    APPROVAL_TYPES,
    display_title,
    sanitize_excerpt,
    truncate,
    resolve_action,
)

APPROVAL_STATUSES = ("pending", "approved", "rejected")

_STATUS_TO_ACTION = {"approved": "approve", "rejected": "reject"}


def classification_to_row(classification: dict, user_id: str, source_file: str, body: str) -> dict:
    """Build an ``approvals`` table row from a slack_approvals classification.

    ``classification`` is the dict returned by
    ``tools.slack_approvals.classify_outbox_file`` — never ``None`` here;
    callers must skip non-approval outbox files before calling this.
    ``body`` is the raw outbox file content, sanitized and truncated here
    exactly as the Slack daemon does for its Block Kit message.
    """
    request_type = classification["request_type"]
    if request_type not in APPROVAL_TYPES:
        raise ValueError(f"unknown request_type: {request_type!r}")
    if not user_id:
        raise ValueError("user_id is required to stamp an approvals row")

    return {
        "user_id": user_id,
        "request_type": request_type,
        "request_id": classification["request_id"],
        "source_file": source_file,
        "title": display_title(request_type),
        "body": truncate(sanitize_excerpt(body)),
        "status": "pending",
    }


def decision_to_inbox_write(row: dict) -> dict:
    """Decide what an approvals-table row's decision means for the inbox side.

    Pure, no I/O. Returns
    ``{"should_write": bool, "inbox_filename": str|None, "content": str|None, "outcome": str|None}``.

    A ``status`` of ``"pending"`` (not yet decided) is a no-op: nothing to
    write, ``outcome`` is ``None``. Otherwise defers to
    ``tools.slack_approvals.resolve_action`` for the exact same
    approve/reject-to-inbox-file mapping the Slack daemon uses.
    """
    status = row.get("status")
    if status not in APPROVAL_STATUSES:
        raise ValueError(f"unknown status: {status!r}")

    if status == "pending":
        return {"should_write": False, "inbox_filename": None, "content": None, "outcome": None}

    action = _STATUS_TO_ACTION[status]
    return resolve_action(row["request_type"], row["request_id"], action)


def is_already_decided(row: dict) -> bool:
    """True once a founder (via the app, or the Slack daemon) has resolved this row."""
    return row.get("status") in ("approved", "rejected")


def needs_inbox_sync(row: dict) -> bool:
    """True when a decided row hasn't yet had its inbox fulfillment file written."""
    return is_already_decided(row) and not row.get("inbox_synced_at")
