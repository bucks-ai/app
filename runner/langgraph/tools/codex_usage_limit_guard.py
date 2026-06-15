"""Codex usage-limit guard.

Detects when the Codex CLI returns errors that indicate the OpenAI account has
hit a usage or rate limit (HTTP 429, quota exhaustion, monthly cap) and halts
the loop once the count reaches the configured ceiling.  A single usage-limit
error may be transient (brief rate-limit window); repeated errors almost
certainly mean the account's quota is exhausted for the billing period.

The decision logic here is pure (no disk/network I/O, no state mutation) so it
is unit-testable in isolation.  The graph node in ``graph.update_logs_and_state``
does the state mutation around it.  This mirrors the pure-helper + thin-node
pattern used by ``tools/worker_timeout_guard.py``.
"""
from typing import Optional

CODEX_USAGE_LIMIT_STOP = "codex_usage_limit"

_USAGE_LIMIT_MARKERS = (
    "429",
    "rate limit",
    "rate_limit",
    "quota",
    "usage limit",
    "monthly limit",
    "too many requests",
    "insufficient_quota",
    "billing hard limit",
)


def _is_usage_limit_error(error: Optional[str]) -> bool:
    """True when the error string looks like a Codex/OpenAI usage-limit response."""
    if not error:
        return False
    lower = error.lower()
    return any(marker in lower for marker in _USAGE_LIMIT_MARKERS)


def evaluate_codex_usage_limit(
    error: Optional[str],
    worker: Optional[str],
    usage_limit_count: int,
    max_codex_usage_limit_errors: int,
) -> dict:
    """Decide whether this run hit a Codex usage limit and whether to halt.

    Args:
        error:                        Worker error string (may be None on success).
        worker:                       Worker name (e.g. ``"codex"``).
        usage_limit_count:            Usage-limit errors recorded so far this session
                                      (not including the current run).
        max_codex_usage_limit_errors: Trip the breaker when the new count reaches
                                      this.  ``<= 0`` disables the guard entirely.

    Returns a dict with:
        - ``usage_limit_detected`` — True if this run looks like a usage-limit error.
        - ``usage_limit_count``    — Updated count (prior + 1 if detected else prior).
        - ``blocked``              — True when the guard should trip.
        - ``stop_reason``          — ``CODEX_USAGE_LIMIT_STOP`` when blocked, else None.
    """
    if max_codex_usage_limit_errors <= 0 or worker != "codex":
        return {
            "usage_limit_detected": False,
            "usage_limit_count": usage_limit_count,
            "blocked": False,
            "stop_reason": None,
        }

    detected = _is_usage_limit_error(error)
    new_count = (usage_limit_count + 1) if detected else usage_limit_count
    blocked = new_count >= max_codex_usage_limit_errors

    return {
        "usage_limit_detected": detected,
        "usage_limit_count": new_count,
        "blocked": blocked,
        "stop_reason": CODEX_USAGE_LIMIT_STOP if blocked else None,
    }
