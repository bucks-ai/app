"""Unit tests for the worker health probe.

Runs standalone (no pytest dependency):

    python tests/test_worker_health_probe.py

Covers the pure helper ``probe_worker_health()`` in
``tools/worker_health_probe.py``.  The binary-availability check (``shutil.which``)
is monkey-patched so tests do not depend on the actual host PATH.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tools.worker_health_probe as whp
from tools.worker_health_probe import probe_worker_health, WORKER_HEALTH_STOP


def _with_which(found: bool):
    """Context manager that stubs shutil.which to return a path or None."""
    import contextlib

    @contextlib.contextmanager
    def cm():
        original = whp._binary_available
        whp._binary_available = lambda _: "fake-binary" if found else None
        try:
            yield
        finally:
            whp._binary_available = original

    return cm()


# ---------------------------------------------------------------------------
# Guard disabled
# ---------------------------------------------------------------------------

def test_probe_disabled_always_available():
    with _with_which(False):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=False,
            has_openai=False,
            health_probe_enabled=False,
        )
    assert r["available"] is True
    assert r["blocked"] is False
    assert r["stop_reason"] is None


# ---------------------------------------------------------------------------
# Claude worker
# ---------------------------------------------------------------------------

def test_claude_happy_path_api_key():
    with _with_which(True):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=True,
            has_openai=False,
        )
    assert r["available"] is True
    assert r["blocked"] is False
    assert r["stop_reason"] is None


def test_claude_happy_path_subscription():
    with _with_which(True):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="subscription",
            has_anthropic=False,
            has_openai=False,
        )
    assert r["available"] is True
    assert r["blocked"] is False


def test_claude_missing_binary():
    with _with_which(False):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=True,
            has_openai=False,
        )
    assert r["available"] is False
    assert r["blocked"] is True
    assert r["stop_reason"] == WORKER_HEALTH_STOP
    assert "binary" in r["reason"]


def test_claude_missing_api_key():
    with _with_which(True):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=False,
            has_openai=False,
        )
    assert r["available"] is False
    assert r["blocked"] is True
    assert r["stop_reason"] == WORKER_HEALTH_STOP
    assert "ANTHROPIC_API_KEY" in r["reason"]


def test_claude_subscription_no_key_needed():
    with _with_which(True):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="subscription",
            has_anthropic=False,
            has_openai=False,
        )
    assert r["available"] is True


# ---------------------------------------------------------------------------
# Codex worker
# ---------------------------------------------------------------------------

def test_codex_happy_path():
    with _with_which(True):
        r = probe_worker_health(
            "codex",
            claude_auth_mode="api_key",
            has_anthropic=False,
            has_openai=True,
        )
    assert r["available"] is True
    assert r["blocked"] is False


def test_codex_missing_binary():
    with _with_which(False):
        r = probe_worker_health(
            "codex",
            claude_auth_mode="api_key",
            has_anthropic=False,
            has_openai=True,
        )
    assert r["available"] is False
    assert r["stop_reason"] == WORKER_HEALTH_STOP
    assert "binary" in r["reason"]


def test_codex_missing_openai_key():
    with _with_which(True):
        r = probe_worker_health(
            "codex",
            claude_auth_mode="api_key",
            has_anthropic=False,
            has_openai=False,
        )
    assert r["available"] is False
    assert "OPENAI_API_KEY" in r["reason"]


# ---------------------------------------------------------------------------
# Unknown worker type passes through
# ---------------------------------------------------------------------------

def test_unknown_worker_type_passes():
    with _with_which(False):
        r = probe_worker_health(
            "chatgpt",
            claude_auth_mode="api_key",
            has_anthropic=False,
            has_openai=False,
        )
    assert r["available"] is True
    assert r["blocked"] is False


def test_result_echoes_worker_type():
    with _with_which(True):
        r = probe_worker_health(
            "codex",
            claude_auth_mode="api_key",
            has_anthropic=False,
            has_openai=True,
        )
    assert r["worker"] == "codex"


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_probe_disabled_always_available,
        test_claude_happy_path_api_key,
        test_claude_happy_path_subscription,
        test_claude_missing_binary,
        test_claude_missing_api_key,
        test_claude_subscription_no_key_needed,
        test_codex_happy_path,
        test_codex_missing_binary,
        test_codex_missing_openai_key,
        test_unknown_worker_type_passes,
        test_result_echoes_worker_type,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
