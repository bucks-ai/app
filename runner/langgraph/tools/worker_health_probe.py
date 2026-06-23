"""Worker health probe.

Performs a lightweight pre-dispatch check before a worker is invoked to
detect obvious unavailability early — missing credentials, absent CLI
binaries — without making any LLM API calls.  Catching these conditions
before dispatching avoids burning a full task slot on a certain failure and
lets the runner log a clear diagnostic rather than a generic worker error.

The check is intentionally cheap (filesystem + env-var lookups only) so it
adds negligible latency to each loop iteration.

Design: pure helper ``probe_worker_health()`` returns a plain dict so it is
unit-testable without patching graph or file-system state, following the same
pure-helper + thin-node pattern used by ``tools/failure_guard.py``.
"""
from __future__ import annotations

import shutil
from typing import Optional

WORKER_HEALTH_STOP = "worker_health_probe_failed"

_CLAUDE_BINARIES = ("claude",)
_CODEX_BINARIES = ("codex",)


def _binary_available(candidates: tuple[str, ...]) -> Optional[str]:
    """Return the first binary name found on PATH, or None."""
    for name in candidates:
        if shutil.which(name):
            return name
    return None


def probe_worker_health(
    worker_type: str,
    claude_auth_mode: str,
    has_anthropic: bool,
    has_openai: bool,
    health_probe_enabled: bool = True,
) -> dict:
    """Check whether the chosen worker appears ready to accept work.

    Args:
        worker_type:         ``"claude"`` or ``"codex"`` (other values pass).
        claude_auth_mode:    ``"api_key"`` or ``"subscription"``.
        has_anthropic:       True when ``ANTHROPIC_API_KEY`` is set.
        has_openai:          True when ``OPENAI_API_KEY`` is set.
        health_probe_enabled: When False the function is a no-op that always
                              returns ``available=True``.

    Returns a dict with:
        - ``available``   — True when the worker appears ready.
        - ``worker``      — Echo of ``worker_type``.
        - ``reason``      — Human-readable explanation when not available.
        - ``blocked``     — True when the runner should halt (same as
                            ``not available`` when probe is enabled).
        - ``stop_reason`` — ``WORKER_HEALTH_STOP`` when blocked, else None.
    """
    if not health_probe_enabled:
        return {
            "available": True,
            "worker": worker_type,
            "reason": None,
            "blocked": False,
            "stop_reason": None,
        }

    available = True
    reason: Optional[str] = None

    if worker_type == "claude":
        cli_found = _binary_available(_CLAUDE_BINARIES)
        creds_ok = claude_auth_mode == "subscription" or has_anthropic
        if not cli_found:
            available = False
            reason = "claude CLI binary not found on PATH"
        elif not creds_ok:
            available = False
            reason = (
                "Claude requires ANTHROPIC_API_KEY (api_key mode) "
                "or CLAUDE_AUTH_MODE=subscription"
            )
    elif worker_type == "codex":
        cli_found = _binary_available(_CODEX_BINARIES)
        if not cli_found:
            available = False
            reason = "codex CLI binary not found on PATH"
        elif not has_openai:
            available = False
            reason = "Codex requires OPENAI_API_KEY"

    blocked = not available
    return {
        "available": available,
        "worker": worker_type,
        "reason": reason,
        "blocked": blocked,
        "stop_reason": WORKER_HEALTH_STOP if blocked else None,
    }
