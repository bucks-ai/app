"""Connectivity probe for network-pause detection (M4c.4).

Single authority for "the machine is offline." Two-step probe:
  1. DNS resolution of a well-known hostname
  2. A lightweight HEAD request to a well-known HTTP endpoint

Online if either step succeeds. A single failing provider endpoint does not
indicate network loss — the probe must fail both tests before concluding offline.

Also exports ``is_network_error_string`` to classify mid-call exception
messages as network-shaped. Rate-limit (429) and auth (401/403) errors are
never classified as network loss — those take their existing retry and
cooldown paths.
"""
from __future__ import annotations

import re
import socket
import urllib.error
import urllib.request
from typing import Callable, Optional

# Probe targets — no credentials, no auth, no tokens spent.
_DNS_HOST = "dns.google"                         # stable public hostname
_HTTP_URL = "https://www.gstatic.com/generate_204"  # Google connectivity check, returns 204
_DEFAULT_TIMEOUT_S = 5

# Exception class names indicating network-layer failure.
_NETWORK_EXCEPTION_NAMES = frozenset({
    "ConnectionError",
    "ConnectionResetError",
    "ConnectionAbortedError",
    "ConnectionRefusedError",
    "ConnectTimeout",
    "ReadTimeout",
    "TimeoutError",
    "URLError",
    "gaierror",
    "herror",
    "timeout",
    "socket.timeout",
    "NewConnectionError",
    "MaxRetryError",
    "APIConnectionError",
    "APITimeoutError",
    "ProtocolError",
    "RemoteDisconnected",
    "IncompleteRead",
})

# Error message fragments indicating network-layer failure (not provider errors).
# Deliberately excludes rate-limit and server-error patterns — those keep their
# existing retry/cooldown paths.
_NETWORK_ERROR_PATTERNS = (
    "name or service not known",
    "temporary failure in name resolution",
    "nodename nor servname",
    "getaddrinfo failed",
    "name resolution",
    "could not resolve host",
    "dns lookup",
    "network is unreachable",
    "network unreachable",
    "no route to host",
    "connection reset",
    "connection refused",
    "connection aborted",
    "connection timed out",
    "connect timeout",
    "read timeout",
    "request timed out",
    "operation timed out",
    "etimedout",
    "broken pipe",
    "remote end closed connection",
    "eof occurred in violation of protocol",
    "ssl handshake",
    "tls handshake",
)

# Patterns that mean a specific provider had trouble — NOT network loss.
# If any of these appear we refuse to classify as offline.
_NOT_NETWORK_TEXT_PATTERNS = (
    "rate limit",
    "rate-limited",
    "too many requests",
    "slow down",
    "unauthorized",
    "forbidden",
    "internal server error",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "server overloaded",
)

# Regex for HTTP status codes that indicate provider-level errors (4xx auth, 429, 5xx).
# Uses anchored context so "5000ms" or "503rd" don't match.
_HTTP_STATUS_PROVIDER_RE = re.compile(
    r"(?:http(?:\s+error)?|status(?:\s+code)?|code|error|response)\s*[:=]?\s*(401|403|429|5\d{2})\b",
    re.IGNORECASE,
)


def probe_connectivity(
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    *,
    probe_fn: Optional[Callable] = None,
) -> dict:
    """Test connectivity via DNS resolution + HEAD request.

    Returns::

        {
          "online":  bool,
          "detail":  str,      # human-readable description of what happened
          "dns_ok":  bool,
          "http_ok": bool,
        }

    ``probe_fn`` is for testing only: called as ``probe_fn(timeout_s)`` and
    must return ``{"dns_ok": bool, "http_ok": bool}``.  When provided, the
    real DNS/HTTP calls are skipped entirely.
    """
    if probe_fn is not None:
        result = probe_fn(timeout_s)
        dns_ok = bool(result.get("dns_ok"))
        http_ok = bool(result.get("http_ok"))
        online = dns_ok or http_ok
        return {
            "online": online,
            "detail": f"probe_fn: dns_ok={dns_ok} http_ok={http_ok}",
            "dns_ok": dns_ok,
            "http_ok": http_ok,
        }

    # Step 1: DNS resolution
    dns_ok = False
    dns_detail = ""
    try:
        socket.setdefaulttimeout(timeout_s)
        socket.getaddrinfo(_DNS_HOST, None)
        dns_ok = True
        dns_detail = f"dns resolved {_DNS_HOST!r}"
    except OSError as exc:
        dns_detail = f"dns failed: {exc}"
    finally:
        socket.setdefaulttimeout(None)

    # Step 2: HTTP HEAD request (no credentials, no body)
    http_ok = False
    http_detail = ""
    try:
        req = urllib.request.Request(_HTTP_URL, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            http_ok = resp.status < 500
            http_detail = f"http {resp.status}"
    except urllib.error.HTTPError as exc:
        # An HTTP error means we reached the server — the machine is online.
        http_ok = True
        http_detail = f"http {exc.code} (server reached)"
    except (urllib.error.URLError, OSError) as exc:
        http_detail = f"http failed: {exc}"

    online = dns_ok or http_ok
    detail = "; ".join(p for p in [dns_detail, http_detail] if p)
    return {
        "online": online,
        "detail": detail or "no probe result",
        "dns_ok": dns_ok,
        "http_ok": http_ok,
    }


def is_network_error_string(error: str) -> bool:
    """Return True when *error* looks like a network-layer failure.

    Checks exception class names embedded in the string (e.g. "gaierror",
    "ConnectionResetError") and known network-failure message fragments.

    Returns False for rate-limit (429), auth (401/403), and server-error
    (5xx) patterns — those have their own retry and cooldown paths and must
    never be classified as network loss.
    """
    if not error:
        return False

    err_lower = error.lower()

    # Provider-level errors are NOT network loss.
    if any(p in err_lower for p in _NOT_NETWORK_TEXT_PATTERNS):
        return False
    if _HTTP_STATUS_PROVIDER_RE.search(error):
        return False

    # Exception class names embedded in tracebacks or repr strings.
    for name in _NETWORK_EXCEPTION_NAMES:
        if name.lower() in err_lower:
            return True

    # Substring match on known network-failure phrases.
    return any(p in err_lower for p in _NETWORK_ERROR_PATTERNS)
