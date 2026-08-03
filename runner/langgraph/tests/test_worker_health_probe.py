"""Unit tests for the worker health probe.

Runs standalone (no pytest dependency):

    python tests/test_worker_health_probe.py

Covers the pure helper ``probe_worker_health()`` in
``tools/worker_health_probe.py``.  The binary-availability check (``shutil.which``)
and live-ping subprocess are monkey-patched so tests do not depend on the
actual host PATH or any running CLI.
"""
import contextlib
import os
import subprocess
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tools.worker_health_probe as whp
from tools.worker_health_probe import probe_worker_health, WORKER_HEALTH_STOP


def _with_which(found: bool):
    """Context manager that stubs shutil.which to return a path or None."""
    @contextlib.contextmanager
    def cm():
        original = whp._binary_available
        whp._binary_available = lambda _: "fake-binary" if found else None
        try:
            yield
        finally:
            whp._binary_available = original

    return cm()


def _with_live_ping(alive: bool, latency_ms: float = 42.0, reason: str = None):
    """Context manager that stubs ``_live_ping_binary`` to return a canned result."""
    @contextlib.contextmanager
    def cm():
        original = whp._live_ping_binary
        whp._live_ping_binary = lambda *_a, **_kw: {
            "alive": alive,
            "latency_ms": latency_ms,
            "reason": reason if not alive else None,
        }
        try:
            yield
        finally:
            whp._live_ping_binary = original

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
# Live ping — disabled (default)
# ---------------------------------------------------------------------------

def test_live_ping_off_by_default_no_latency():
    with _with_which(True):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=True,
            has_openai=False,
        )
    assert r["available"] is True
    assert r["live_ping_latency_ms"] is None


def test_live_ping_disabled_skips_subprocess():
    """live_ping_enabled=False must not call _live_ping_binary even if static checks pass."""
    calls = []
    import contextlib

    @contextlib.contextmanager
    def _track():
        original = whp._live_ping_binary
        whp._live_ping_binary = lambda *a, **kw: calls.append(1) or {"alive": True, "latency_ms": 0, "reason": None}
        try:
            yield
        finally:
            whp._live_ping_binary = original

    with _with_which(True), _track():
        probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=True,
            has_openai=False,
            live_ping_enabled=False,
        )
    assert calls == [], "subprocess invoked despite live_ping_enabled=False"


# ---------------------------------------------------------------------------
# Live ping — enabled, success
# ---------------------------------------------------------------------------

def test_live_ping_success_available():
    with _with_which(True), _with_live_ping(alive=True, latency_ms=55.0):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=True,
            has_openai=False,
            live_ping_enabled=True,
        )
    assert r["available"] is True
    assert r["blocked"] is False
    assert r["live_ping_latency_ms"] == 55.0


def test_live_ping_codex_success():
    with _with_which(True), _with_live_ping(alive=True, latency_ms=80.0):
        r = probe_worker_health(
            "codex",
            claude_auth_mode="api_key",
            has_anthropic=False,
            has_openai=True,
            live_ping_enabled=True,
        )
    assert r["available"] is True
    assert r["live_ping_latency_ms"] == 80.0


# ---------------------------------------------------------------------------
# Live ping — enabled, failure
# ---------------------------------------------------------------------------

def test_live_ping_failure_marks_unavailable():
    with _with_which(True), _with_live_ping(alive=False, latency_ms=12.0, reason="claude --version exited with code 1"):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=True,
            has_openai=False,
            live_ping_enabled=True,
        )
    assert r["available"] is False
    assert r["blocked"] is True
    assert r["stop_reason"] == WORKER_HEALTH_STOP
    assert "exited with code 1" in r["reason"]
    assert r["live_ping_latency_ms"] == 12.0


def test_live_ping_timeout_marks_unavailable():
    with _with_which(True), _with_live_ping(alive=False, latency_ms=10001.0, reason="claude --version timed out after 10.0s"):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=True,
            has_openai=False,
            live_ping_enabled=True,
        )
    assert r["available"] is False
    assert "timed out" in r["reason"]
    assert r["live_ping_latency_ms"] == 10001.0


# ---------------------------------------------------------------------------
# Live ping skipped when static checks already fail
# ---------------------------------------------------------------------------

def test_live_ping_not_run_when_static_fails():
    """If static check fails, live ping must not be invoked."""
    calls = []
    import contextlib

    @contextlib.contextmanager
    def _track():
        original = whp._live_ping_binary
        whp._live_ping_binary = lambda *a, **kw: calls.append(1) or {"alive": True, "latency_ms": 0, "reason": None}
        try:
            yield
        finally:
            whp._live_ping_binary = original

    with _with_which(False), _track():
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=True,
            has_openai=False,
            live_ping_enabled=True,
        )
    assert r["available"] is False
    assert calls == [], "live ping invoked despite static binary check failure"
    assert r["live_ping_latency_ms"] is None


def test_live_ping_latency_none_on_static_failure():
    with _with_which(False), _with_live_ping(alive=True, latency_ms=50.0):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=True,
            has_openai=False,
            live_ping_enabled=True,
        )
    assert r["live_ping_latency_ms"] is None


# ---------------------------------------------------------------------------
# _live_ping_binary unit tests
# ---------------------------------------------------------------------------

def test_live_ping_binary_success():
    """Stub subprocess.run to simulate a fast exit-0 response."""
    import contextlib

    class _FakeProc:
        returncode = 0
        stderr = b""

    @contextlib.contextmanager
    def _stub_run():
        original = whp.subprocess.run
        whp.subprocess.run = lambda *a, **kw: _FakeProc()
        try:
            yield
        finally:
            whp.subprocess.run = original

    with _stub_run():
        result = whp._live_ping_binary("claude", timeout_s=5.0)
    assert result["alive"] is True
    assert result["reason"] is None
    assert result["latency_ms"] >= 0


def test_live_ping_binary_nonzero_exit():
    import contextlib

    class _FakeProc:
        returncode = 1
        stderr = b"error detail"

    @contextlib.contextmanager
    def _stub_run():
        original = whp.subprocess.run
        whp.subprocess.run = lambda *a, **kw: _FakeProc()
        try:
            yield
        finally:
            whp.subprocess.run = original

    with _stub_run():
        result = whp._live_ping_binary("claude", timeout_s=5.0)
    assert result["alive"] is False
    assert "code 1" in result["reason"]
    assert "error detail" in result["reason"]


def test_live_ping_binary_timeout():
    import contextlib

    @contextlib.contextmanager
    def _stub_run():
        original = whp.subprocess.run

        def _raise(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="claude", timeout=5.0)

        whp.subprocess.run = _raise
        try:
            yield
        finally:
            whp.subprocess.run = original

    with _stub_run():
        result = whp._live_ping_binary("claude", timeout_s=5.0)
    assert result["alive"] is False
    assert "timed out" in result["reason"]


def test_live_ping_binary_not_found():
    import contextlib

    @contextlib.contextmanager
    def _stub_run():
        original = whp.subprocess.run

        def _raise(*a, **kw):
            raise FileNotFoundError("no such file")

        whp.subprocess.run = _raise
        try:
            yield
        finally:
            whp.subprocess.run = original

    with _stub_run():
        result = whp._live_ping_binary("ghost-binary", timeout_s=5.0)
    assert result["alive"] is False
    assert "not found" in result["reason"]


# ---------------------------------------------------------------------------
# Probe disabled still returns live_ping_latency_ms=None
# ---------------------------------------------------------------------------

def test_probe_disabled_live_ping_latency_none():
    with _with_which(False):
        r = probe_worker_health(
            "claude",
            claude_auth_mode="api_key",
            has_anthropic=False,
            has_openai=False,
            health_probe_enabled=False,
            live_ping_enabled=True,
        )
    assert r["available"] is True
    assert r["live_ping_latency_ms"] is None


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
        test_live_ping_off_by_default_no_latency,
        test_live_ping_disabled_skips_subprocess,
        test_live_ping_success_available,
        test_live_ping_codex_success,
        test_live_ping_failure_marks_unavailable,
        test_live_ping_timeout_marks_unavailable,
        test_live_ping_not_run_when_static_fails,
        test_live_ping_latency_none_on_static_failure,
        test_live_ping_binary_success,
        test_live_ping_binary_nonzero_exit,
        test_live_ping_binary_timeout,
        test_live_ping_binary_not_found,
        test_probe_disabled_live_ping_latency_none,
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
