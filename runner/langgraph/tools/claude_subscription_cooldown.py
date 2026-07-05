# DESTINATION: runner/langgraph/tools/claude_subscription_cooldown.py  (full replacement)
"""Claude subscription cooldown auto-resume guard.

When Claude is used in subscription mode (``CLAUDE_AUTH_MODE=subscription``)
the Claude.ai rate-limiter occasionally returns a cooldown response — e.g.
"Claude usage limit reached. Your limit will reset at 6pm".  Rather than
counting this as a worker failure and eventually halting the loop, this guard
detects the cooldown, computes the resume timestamp, and signals the runner to
pause until Claude is available again.

v2 changes:
- Parses ABSOLUTE reset times ("your limit will reset at 6pm", "resets at
  3:30 PM (America/Los_Angeles)") in addition to relative durations
  ("try again in 2 hours").  Claude Code emits absolute local times, so
  without this the guard always fell back to the default wait.
- Absolute times are interpreted against the machine's LOCAL clock (the
  Claude CLI runs on the same machine, so its reported clock times share
  this timezone).  If the parsed time is in the past, the next day is
  assumed.  A small buffer is added so we never resume a minute early.

Decision logic is pure (no disk/network I/O, no state mutation) so it is
unit-testable in isolation.  The graph node ``update_logs_and_state`` detects
the cooldown and requeues the task; ``decide_continue_or_stop`` performs the
actual wait.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

CLAUDE_COOLDOWN_STOP = "claude_subscription_cooldown"

# Seconds added to any parsed absolute reset time so we never retry seconds
# before the limiter actually resets.
_RESUME_BUFFER_S = 120

_COOLDOWN_MARKERS = (
    "claude usage limit reached",
    "claude ai usage limit",
    "usage limit reached",
    "usage limit exceeded",
    "you've reached your claude",
    "you have reached your usage limit",
    "usage limit will reset",
    "your limit will reset",
    "rate limit exceeded",
    "slowdown",
    "please try again in",
    "try again after",
    "overloaded with requests",
)

# Patterns like "try again in 2 hours", "resets in 47 minutes", "wait 30 minutes"
_DURATION_PATTERNS = (
    re.compile(r"(?:in|after|wait(?:ing)?)\s+(\d+)\s+hour", re.IGNORECASE),
    re.compile(r"(?:in|after|wait(?:ing)?)\s+(\d+)\s+minute", re.IGNORECASE),
    re.compile(r"resets?\s+(?:in|after)\s+(\d+)\s+hour", re.IGNORECASE),
    re.compile(r"resets?\s+(?:in|after)\s+(\d+)\s+minute", re.IGNORECASE),
)

# Patterns like "reset at 6pm", "resets at 3:30 PM", "will reset at 18:00",
# optionally followed by a timezone name we ignore (local clock is used).
_ABSOLUTE_PATTERNS = (
    re.compile(
        r"resets?\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:available|try)\s+(?:again\s+)?at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        re.IGNORECASE,
    ),
)


def _is_cooldown_error(output: Optional[str], error: Optional[str]) -> bool:
    """True when the worker response contains a Claude subscription cooldown signal."""
    text = " ".join(filter(None, [output, error])).lower()
    return any(marker in text for marker in _COOLDOWN_MARKERS)


def _parse_absolute_wait_seconds(
    text: str,
    local_now: datetime,
) -> Optional[int]:
    """Parse an absolute clock time ("resets at 6pm") into seconds-from-now.

    Interprets the clock time against ``local_now`` (the machine's local
    clock — same timezone the Claude CLI reports in).  Returns None when no
    absolute time is present or the parse is not plausible.
    """
    for pattern in _ABSOLUTE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        meridiem = (m.group(3) or "").lower()

        if minute > 59:
            continue
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        elif not meridiem:
            # No am/pm: accept 0-23 as 24h clock; ambiguous 1-11 is taken
            # as-is (worst case we wake early and re-detect the cooldown).
            pass
        if hour > 23:
            continue

        candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= local_now:
            candidate += timedelta(days=1)

        wait = int((candidate - local_now).total_seconds()) + _RESUME_BUFFER_S
        return wait
    return None


def _parse_wait_seconds(
    output: Optional[str],
    error: Optional[str],
    default_wait_s: int,
    local_now: Optional[datetime] = None,
) -> int:
    """Parse cooldown duration from the response text.

    Order: relative duration ("in 2 hours") → absolute clock time
    ("resets at 6pm") → ``default_wait_s``.
    """
    text = " ".join(filter(None, [output, error]))
    for pattern in _DURATION_PATTERNS:
        m = pattern.search(text)
        if m:
            value = int(m.group(1))
            if "hour" in pattern.pattern:
                return value * 3600
            return value * 60

    absolute = _parse_absolute_wait_seconds(text, local_now or datetime.now())
    if absolute is not None:
        return absolute

    return default_wait_s


def evaluate_subscription_cooldown(
    output: Optional[str],
    error: Optional[str],
    worker: Optional[str],
    auth_mode: str,
    enabled: bool,
    default_wait_s: int,
    cooldown_count: int,
    max_cooldown_waits: int,
    *,
    _now: Optional[datetime] = None,
    _local_now: Optional[datetime] = None,
) -> dict:
    """Decide whether this run hit a Claude subscription cooldown.

    Args:
        output:             Worker stdout / output text (may be None).
        error:              Worker error string (may be None).
        worker:             Worker name — only ``"claude"`` triggers this guard.
        auth_mode:          ``"api_key"`` or ``"subscription"``.
        enabled:            When False the guard is a no-op.
        default_wait_s:     Seconds to wait when the cooldown duration cannot
                            be parsed from the response text (default 3600).
        cooldown_count:     Cooldown events recorded so far this session.
        max_cooldown_waits: Halt the loop rather than waiting when the count
                            reaches this ceiling.  ``<= 0`` disables the limit.
        _now:               Override for the current UTC time (testing only).
        _local_now:         Override for the current LOCAL time (testing only;
                            used for absolute clock-time parsing).

    Returns a dict with:
        - ``detected``          — True when a cooldown was found.
        - ``wait_seconds``      — How long to wait before resuming.
        - ``resume_at_iso``     — ISO-8601 UTC timestamp after which to retry.
        - ``cooldown_count``    — Updated count (prior + 1 if detected else prior).
        - ``blocked``           — True when ``max_cooldown_waits`` is reached and
                                  the loop should halt rather than wait.
        - ``stop_reason``       — ``CLAUDE_COOLDOWN_STOP`` when blocked, else None.
    """
    _no_op = {
        "detected": False,
        "wait_seconds": 0,
        "resume_at_iso": None,
        "cooldown_count": cooldown_count,
        "blocked": False,
        "stop_reason": None,
    }

    if not enabled or worker != "claude" or auth_mode != "subscription":
        return _no_op

    if not _is_cooldown_error(output, error):
        return _no_op

    wait_s = _parse_wait_seconds(output, error, default_wait_s, local_now=_local_now)
    now = _now or datetime.utcnow()
    resume_at = (now + timedelta(seconds=wait_s)).isoformat()
    new_count = cooldown_count + 1

    blocked = max_cooldown_waits > 0 and new_count >= max_cooldown_waits

    return {
        "detected": True,
        "wait_seconds": wait_s,
        "resume_at_iso": resume_at,
        "cooldown_count": new_count,
        "blocked": blocked,
        "stop_reason": CLAUDE_COOLDOWN_STOP if blocked else None,
    }
