"""Retry utility for transient HTTP failures.

Provides ``retry_request(fn, *args, **kwargs)`` — a thin wrapper that calls
``fn`` with exponential backoff for connection errors, timeouts, 5xx responses,
and 429 rate-limit responses. Non-transient failures (4xx except 429) are
re-raised immediately without retrying.

Configuration is read from ``RunnerConfig`` at call time, so env overrides
applied after import still take effect.
"""
import time
import urllib.error

import requests

from config import get_config
from tools.log_tools import log_event


def _is_transient(exc: Exception) -> bool:
    """Return True when the exception represents a transient failure worth retrying."""
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        resp = getattr(exc, "response", None)
        if resp is not None:
            return resp.status_code >= 500 or resp.status_code == 429
        return False
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500 or exc.code == 429
    if isinstance(exc, urllib.error.URLError):
        return True
    return False


def retry_request(fn, *args, _sleep=time.sleep, **kwargs):
    """Call ``fn(*args, **kwargs)`` with retry on transient HTTP failures.

    When ``http_retry_enabled`` is False in config, calls ``fn`` exactly once.
    Otherwise retries up to ``http_retry_attempts`` times with exponential
    backoff capped at ``http_retry_max_wait_s``.

    ``_sleep`` is injectable for testing (avoids real sleeps in unit tests).
    """
    cfg = get_config()
    if not cfg.http_retry_enabled:
        return fn(*args, **kwargs)

    max_attempts = cfg.http_retry_attempts
    initial_wait = cfg.http_retry_initial_wait_s
    max_wait = cfg.http_retry_max_wait_s

    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not _is_transient(exc) or attempt >= max_attempts:
                raise
            wait_s = min(initial_wait * (2 ** (attempt - 1)), max_wait)
            log_event("http_retry", {
                "attempt": attempt,
                "max_attempts": max_attempts,
                "wait_s": round(wait_s, 2),
                "error": str(exc),
            })
            _sleep(wait_s)
