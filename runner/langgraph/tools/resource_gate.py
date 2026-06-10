"""Resource & credential request gate.

When a worker reports that it needs a credential (API key, token, secret) or an
external resource it does not yet have, the runner must pause and surface a
human-actionable request — rather than committing/deploying incomplete work or
silently looping past the gap. This mirrors the SQL approval gate
(see ``graph.apply_sql_if_needed``): the request is written to ``outbox/`` for a
human, and the loop only proceeds once a fulfillment file lands in ``inbox/``.

Security: the worker reports only the *names* of needed credentials
(e.g. ``STRIPE_API_KEY``), never their values, so nothing secret is written or
logged here. The human-supplied fulfillment file in ``inbox/`` is treated purely
as an "unblock" signal — its contents are never read or logged — so secrets stay
out of the flight recorder. See AGENTS.md ("Never print secrets").

The functions here are pure (no disk/network I/O) so the gate decision is
unit-testable; the graph node in ``graph.request_resources_if_needed`` does the
file I/O and state mutation around them.
"""
from typing import Optional

# Values a worker may write under a "needed" section that mean "nothing", so an
# empty/placeholder bullet never blocks the loop.
_PLACEHOLDERS = frozenset({
    "", "none", "n/a", "na", "(none)", "(n/a)", "-", "—", "nil", "null", "nothing",
})


def _meaningful(item: Optional[str]) -> bool:
    return bool(item) and item.strip().lower() not in _PLACEHOLDERS


def collect_requests(summary: Optional[dict]) -> dict:
    """Collect the credential/resource needs reported in a parsed worker summary.

    Returns ``{"credentials": [...], "resources": [...], "all": [...]}`` with
    placeholder/empty entries (``none``, ``N/A``, …) filtered out.
    """
    summary = summary or {}
    credentials = [s.strip() for s in (summary.get("credentials_needed") or []) if _meaningful(s)]
    resources = [s.strip() for s in (summary.get("resources_needed") or []) if _meaningful(s)]
    return {
        "credentials": credentials,
        "resources": resources,
        "all": credentials + resources,
    }


def evaluate_gate(summary: Optional[dict], provided: bool) -> dict:
    """Decide the gate state for a parsed summary.

    ``provided`` is whether the human fulfillment file already exists.

    Returns ``{"blocked": bool, "status": str, "requests": dict}`` where status
    is one of ``"none"`` (nothing requested), ``"fulfilled"`` (requested and the
    human signalled fulfillment), or ``"pending"`` (requested, not yet fulfilled
    → the loop must pause).
    """
    requests = collect_requests(summary)
    if not requests["all"]:
        return {"blocked": False, "status": "none", "requests": requests}
    if provided:
        return {"blocked": False, "status": "fulfilled", "requests": requests}
    return {"blocked": True, "status": "pending", "requests": requests}


def format_request_file(task_id: str, title: str, requests: dict, inbox_filename: str) -> str:
    """Build the human-readable request written to ``outbox/`` (no secret values)."""
    lines = [
        f"# Resource / Credential Request — task: {task_id}",
        f"# Title: {title}",
        "",
        "The worker reported it cannot complete this task without the following.",
        "Provision each item (add the credential to .env / your secret store, or",
        "grant the required access), then create this file to unblock the runner:",
        "",
        f"    inbox/{inbox_filename}",
        "",
    ]
    if requests["credentials"]:
        lines.append("## Credentials needed")
        lines += [f"- {c}" for c in requests["credentials"]]
        lines.append("")
    if requests["resources"]:
        lines.append("## Resources needed")
        lines += [f"- {r}" for r in requests["resources"]]
        lines.append("")
    lines.append(
        "NOTE: Do NOT paste secret values into this file or the inbox file — the "
        "inbox file is used only as an 'unblock' signal and its contents are never "
        "read or logged. Put real secrets in .env / your secret store."
    )
    return "\n".join(lines) + "\n"
