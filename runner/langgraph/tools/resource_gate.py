"""Resource & credential request gate.

When a worker reports that it needs a credential (API key, token, secret) or an
external resource it does not yet have, the runner must set that task aside and
surface a human-actionable request — rather than committing/deploying
incomplete work or silently looping past the gap. This mirrors the SQL approval
gate (see ``graph.apply_sql_if_needed``): the request is written to ``outbox/``
for a human, and the task resumes once a fulfillment file lands in ``inbox/``.

Two M4c.0 corrections apply here. First, the gate consults the authority on
whether a credential exists — the runner's own config/env — before asking a
human for it (``filter_satisfied_credentials``). Second, the block is scoped to
the task, not the run: one task waiting on a credential must not strand the
other nine (see ``tools/gate_authority.py``).

Security: the worker reports only the *names* of needed credentials
(e.g. ``STRIPE_API_KEY``), never their values, so nothing secret is written or
logged here. The human-supplied fulfillment file in ``inbox/`` is treated purely
as an "unblock" signal — its contents are never read or logged — so secrets stay
out of the flight recorder. See AGENTS.md ("Never print secrets").

The functions here are pure (no disk/network I/O) so the gate decision is
unit-testable; the graph node in ``graph.request_resources_if_needed`` does the
file I/O and state mutation around them.
"""
import dataclasses
import os
import re
from typing import Iterable, Optional

# Values a worker may write under a "needed" section that mean "nothing", so an
# empty/placeholder bullet never blocks the loop.
_PLACEHOLDERS = frozenset({
    "", "none", "n/a", "na", "(none)", "(n/a)", "-", "—", "nil", "null", "nothing",
})

# Env-var-shaped tokens inside a request line: SCREAMING_SNAKE_CASE with at
# least one underscore, so prose like "Vercel token" never matches by accident.
_ENV_NAME_RE = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")


def _meaningful(item: Optional[str]) -> bool:
    return bool(item) and item.strip().lower() not in _PLACEHOLDERS


def env_names_in(item: str) -> list[str]:
    """Env-var names mentioned in one request line, e.g.
    ``"VERCEL_TOKEN (deploy scope)"`` → ``["VERCEL_TOKEN"]``.

    Upper-cased first so a worker writing ``vercel_token`` still matches.
    """
    return _ENV_NAME_RE.findall((item or "").upper())


def available_credential_names(environ: Optional[dict] = None, config=None) -> set:
    """Names of credentials the runner *already has*, from env and config.

    Only names are collected — values are read solely to test for emptiness and
    are never returned, logged, or written anywhere (AGENTS.md: "Never print
    secrets"). ``config`` is the ``RunnerConfig`` dataclass, whose lower-case
    field names map onto their env-var spellings (``vercel_token`` →
    ``VERCEL_TOKEN``), so a credential set through config defaults counts too.
    """
    environ = os.environ if environ is None else environ
    names = {
        str(k).upper()
        for k, v in environ.items()
        if isinstance(v, str) and v.strip()
    }
    if config is not None and dataclasses.is_dataclass(config):
        for f in dataclasses.fields(config):
            value = getattr(config, f.name, None)
            if isinstance(value, str) and value.strip():
                names.add(f.name.upper())
    return names


def filter_satisfied_credentials(
    credentials: Iterable[str],
    available: Optional[set] = None,
) -> dict:
    """Split reported credential needs into those already provisioned and those missing.

    A request line counts as satisfied only when it names at least one
    env-var-shaped credential and *every* name it mentions is present — so
    "VERCEL_TOKEN and VERCEL_PROJECT_ID" is only dropped when both exist, and a
    line naming no env var ("access to the Stripe dashboard") is never
    auto-satisfied.

    Rationale (M4c.0): during M2 and M4b the gate repeatedly halted the whole
    loop asking for VERCEL_TOKEN and VERCEL_PROJECT_ID that were sitting in
    ``.env`` the entire time. Config/env is the authority on whether a
    credential exists; the gate must consult it rather than trust the worker's
    self-report.
    """
    credentials = list(credentials or [])
    if not available:
        return {"missing": credentials, "satisfied": []}

    missing, satisfied = [], []
    for item in credentials:
        names = env_names_in(item)
        if names and all(name in available for name in names):
            satisfied.append(item)
        else:
            missing.append(item)
    return {"missing": missing, "satisfied": satisfied}


def collect_requests(summary: Optional[dict], available: Optional[set] = None) -> dict:
    """Collect the credential/resource needs reported in a parsed worker summary.

    Returns ``{"credentials": [...], "resources": [...], "all": [...],
    "satisfied": [...]}`` with placeholder/empty entries (``none``, ``N/A``, …)
    filtered out. When ``available`` is supplied (see
    ``available_credential_names``), credentials the runner already holds are
    moved out of ``credentials``/``all`` into ``satisfied`` so they cannot block.
    """
    summary = summary or {}
    credentials = [s.strip() for s in (summary.get("credentials_needed") or []) if _meaningful(s)]
    resources = [s.strip() for s in (summary.get("resources_needed") or []) if _meaningful(s)]
    split = filter_satisfied_credentials(credentials, available)
    return {
        "credentials": split["missing"],
        "resources": resources,
        "all": split["missing"] + resources,
        "satisfied": split["satisfied"],
    }


def evaluate_gate(summary: Optional[dict], provided: bool, available: Optional[set] = None) -> dict:
    """Decide the gate state for a parsed summary.

    ``provided`` is whether the human fulfillment file already exists.
    ``available`` filters out credentials the runner already holds.

    Returns ``{"blocked": bool, "status": str, "requests": dict}`` where status
    is one of ``"none"`` (nothing requested), ``"fulfilled"`` (requested and the
    human signalled fulfillment), or ``"pending"`` (requested, not yet fulfilled
    → the task is set aside).
    """
    requests = collect_requests(summary, available)
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
