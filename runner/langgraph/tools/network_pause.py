"""Network connectivity pause guard.

Detects total loss of connectivity — not a single provider going down — as an
environmental PAUSE.  The loop stops claiming or dispatching work, waits in a
polling loop, and resumes within one poll interval after connectivity returns.

Two detection paths:

  (a) Pre-dispatch probe (dispatch_worker): before any worker is launched, a
      cheap DNS + HEAD check confirms the machine is online.  Failure prevents
      dispatch and signals a network pause without touching any counters.

  (b) Mid-call classification (update_logs_and_state): if a worker call
      produces a socket-level error (DNS failure, connection refused/reset, no
      route, TLS handshake, timeout with zero bytes received) the error is
      classified here as a network pause rather than as a task failure.

WHAT IS NOT COVERED: HTTP 5xx from a single provider, HTTP 4xx auth or
rate-limit responses.  Those keep their existing handling.  The probe is the
authority on "the machine is offline"; a failing endpoint is not.

The wait loop runs in decide_continue_or_stop (mirroring the subscription
cooldown machinery).  Nothing is touched while paused: no retry_count, no
task_attempt_counts, no consecutive_failures, no error_history, no task
status change, no Supabase sync, and stale-run watchdog is suppressed by
refreshing last_task_completed_at at both ends of the wait.
"""
from __future__ import annotations

import socket
import urllib.request
import urllib.error
from typing import Optional

NETWORK_PAUSE_STOP = "network_unavailable"

# Probe targets — reliable, lightweight, no authentication required.
_PROBE_HOST = "dns.google"
_PROBE_URL = "http://clients3.google.com/generate_204"

# Socket-level error patterns that indicate total loss of connectivity.
# Conservative: must not match HTTP 5xx / 4xx / rate-limit responses.
_NETWORK_ERROR_PATTERNS = (
    # DNS failures
    "name or service not known",
    "nodename nor servname provided",
    "temporary failure in name resolution",
    "name resolution failed",
    "getaddrinfo failed",
    "[errno -2]",   # EAI_NONAME
    "[errno -3]",   # EAI_AGAIN (temporary DNS failure)
    # Socket-level connection failures
    "connection refused",
    "connection reset by peer",
    "no route to host",
    "network is unreachable",
    "network unreachable",
    "connection timed out",
    # TLS/SSL handshake failures
    "ssl: handshake_failure",
    "tls handshake failure",
    "ssl handshake timed out",
    "ssl: eof occurred in violation of protocol",
    # OS errno codes (bracketed form from Python socket/OSError repr)
    "[errno 101]",  # ENETUNREACH
    "[errno 104]",  # ECONNRESET
    "[errno 110]",  # ETIMEDOUT
    "[errno 111]",  # ECONNREFUSED
    "[errno 113]",  # EHOSTUNREACH
    # Runner-internal marker set by the pre-dispatch probe
    "network_unavailable:",
)

# Patterns that indicate NON-network failures — provider errors, auth, rate
# limits.  Checked FIRST so they take priority over the network patterns.
_NON_NETWORK_PATTERNS = (
    "rate limit",
    "usage limit",
    "subscription",
    "unauthorized",
    "authentication failed",
    "api key",
    "permission denied",
    "forbidden",
    "internal server error",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
)


def probe_connectivity(
    timeout_s: float = 5.0,
    probe_host: str = _PROBE_HOST,
    probe_url: str = _PROBE_URL,
) -> dict:
    """Check whether the machine has internet connectivity.

    Tries DNS resolution of ``probe_host`` first; if that fails, falls back to
    an HTTP request to ``probe_url``.  Either succeeding counts as online.

    Returns:
        {"online": bool, "error": Optional[str]}
    """
    dns_error: Optional[str] = None
    try:
        socket.setdefaulttimeout(timeout_s)
        socket.getaddrinfo(probe_host, None)
        return {"online": True, "error": None}
    except OSError as exc:
        dns_error = str(exc)
    finally:
        socket.setdefaulttimeout(None)

    http_error: Optional[str] = None
    try:
        req = urllib.request.Request(probe_url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            _ = resp.status
        return {"online": True, "error": None}
    except Exception as exc:
        http_error = str(exc)

    return {
        "online": False,
        "error": f"dns: {dns_error}; http: {http_error}",
    }


def is_network_error(error: Optional[str]) -> bool:
    """True when ``error`` is a socket-level connectivity failure.

    Explicitly returns False for provider-specific failures (HTTP 5xx, auth
    errors, rate limits) even if they contain words like "timeout".
    """
    if not error:
        return False
    text = error.lower()

    # Non-network signals take priority over everything else.
    if any(p in text for p in _NON_NETWORK_PATTERNS):
        return False

    return any(p in text for p in _NETWORK_ERROR_PATTERNS)
