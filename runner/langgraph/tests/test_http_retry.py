"""Unit tests for tools/http_retry.py — no network, no real sleeps."""
import os
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from config import get_config
import requests
import requests.exceptions
from tools.http_retry import _is_transient, retry_request


def _cfg(**overrides):
    """Fresh config with optional attribute overrides."""
    config._config = None
    cfg = get_config()
    cfg.http_retry_enabled = overrides.get("http_retry_enabled", True)
    cfg.http_retry_attempts = overrides.get("http_retry_attempts", 3)
    cfg.http_retry_initial_wait_s = overrides.get("http_retry_initial_wait_s", 0.0)
    cfg.http_retry_max_wait_s = overrides.get("http_retry_max_wait_s", 1.0)
    return cfg


# ---------------------------------------------------------------------------
# _is_transient classification
# ---------------------------------------------------------------------------

class TestIsTransient:
    def test_connection_error_is_transient(self):
        assert _is_transient(requests.exceptions.ConnectionError("refused"))

    def test_timeout_is_transient(self):
        assert _is_transient(requests.exceptions.Timeout("timed out"))

    def test_http_error_500_is_transient(self):
        resp = type("R", (), {"status_code": 503})()
        exc = requests.exceptions.HTTPError(response=resp)
        assert _is_transient(exc)

    def test_http_error_429_is_transient(self):
        resp = type("R", (), {"status_code": 429})()
        exc = requests.exceptions.HTTPError(response=resp)
        assert _is_transient(exc)

    def test_http_error_400_not_transient(self):
        resp = type("R", (), {"status_code": 400})()
        exc = requests.exceptions.HTTPError(response=resp)
        assert not _is_transient(exc)

    def test_http_error_404_not_transient(self):
        resp = type("R", (), {"status_code": 404})()
        exc = requests.exceptions.HTTPError(response=resp)
        assert not _is_transient(exc)

    def test_http_error_no_response_not_transient(self):
        exc = requests.exceptions.HTTPError()
        assert not _is_transient(exc)

    def test_urllib_http_error_503_is_transient(self):
        exc = urllib.error.HTTPError("http://x", 503, "err", {}, None)
        assert _is_transient(exc)

    def test_urllib_http_error_429_is_transient(self):
        exc = urllib.error.HTTPError("http://x", 429, "rate", {}, None)
        assert _is_transient(exc)

    def test_urllib_http_error_404_not_transient(self):
        exc = urllib.error.HTTPError("http://x", 404, "not found", {}, None)
        assert not _is_transient(exc)

    def test_urllib_url_error_is_transient(self):
        exc = urllib.error.URLError("connection refused")
        assert _is_transient(exc)

    def test_generic_exception_not_transient(self):
        assert not _is_transient(ValueError("bad value"))

    def test_runtime_error_not_transient(self):
        assert not _is_transient(RuntimeError("unexpected"))


# ---------------------------------------------------------------------------
# retry_request behaviour
# ---------------------------------------------------------------------------

class TestRetryRequest:
    def _no_sleep(self, s):
        self.slept.append(s)

    def setup_method(self):
        self.slept = []

    def test_success_on_first_attempt(self):
        _cfg()
        calls = []

        def fn():
            calls.append(1)
            return "ok"

        result = retry_request(fn, _sleep=self._no_sleep)
        assert result == "ok"
        assert len(calls) == 1
        assert self.slept == []

    def test_retries_on_connection_error(self):
        _cfg(http_retry_attempts=3)
        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 3:
                raise requests.exceptions.ConnectionError("refused")
            return "ok"

        result = retry_request(fn, _sleep=self._no_sleep)
        assert result == "ok"
        assert len(calls) == 3
        assert len(self.slept) == 2

    def test_raises_after_exhausting_attempts(self):
        _cfg(http_retry_attempts=3)

        def fn():
            raise requests.exceptions.Timeout("too slow")

        with pytest.raises(requests.exceptions.Timeout):
            retry_request(fn, _sleep=self._no_sleep)

    def test_non_transient_error_not_retried(self):
        _cfg(http_retry_attempts=3)
        calls = []

        def fn():
            calls.append(1)
            resp = type("R", (), {"status_code": 403})()
            raise requests.exceptions.HTTPError(response=resp)

        with pytest.raises(requests.exceptions.HTTPError):
            retry_request(fn, _sleep=self._no_sleep)

        assert len(calls) == 1, "403 must not trigger a retry"
        assert self.slept == []

    def test_disabled_config_skips_retry(self):
        _cfg(http_retry_enabled=False)
        calls = []

        def fn():
            calls.append(1)
            raise requests.exceptions.ConnectionError("refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            retry_request(fn, _sleep=self._no_sleep)

        assert len(calls) == 1

    def test_backoff_grows_exponentially(self):
        _cfg(http_retry_attempts=4, http_retry_initial_wait_s=1.0, http_retry_max_wait_s=100.0)
        call_count = [0]

        def fn():
            call_count[0] += 1
            raise requests.exceptions.ConnectionError("refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            retry_request(fn, _sleep=self._no_sleep)

        assert self.slept == [1.0, 2.0, 4.0]

    def test_backoff_capped_at_max_wait(self):
        _cfg(http_retry_attempts=4, http_retry_initial_wait_s=5.0, http_retry_max_wait_s=8.0)
        call_count = [0]

        def fn():
            call_count[0] += 1
            raise requests.exceptions.ConnectionError("refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            retry_request(fn, _sleep=self._no_sleep)

        assert all(s <= 8.0 for s in self.slept)

    def test_passes_args_and_kwargs_to_fn(self):
        _cfg()
        received = []

        def fn(a, b, key=None):
            received.append((a, b, key))
            return "done"

        retry_request(fn, 1, 2, _sleep=self._no_sleep, key="val")
        assert received == [(1, 2, "val")]

    def test_urllib_transient_error_retried(self):
        _cfg(http_retry_attempts=2)
        calls = []

        def fn():
            calls.append(1)
            if len(calls) == 1:
                raise urllib.error.URLError("network down")
            return "ok"

        result = retry_request(fn, _sleep=self._no_sleep)
        assert result == "ok"
        assert len(calls) == 2

    def test_urllib_404_not_retried(self):
        _cfg(http_retry_attempts=3)
        calls = []

        def fn():
            calls.append(1)
            raise urllib.error.HTTPError("http://x", 404, "not found", {}, None)

        with pytest.raises(urllib.error.HTTPError):
            retry_request(fn, _sleep=self._no_sleep)

        assert len(calls) == 1

    def test_http_retry_event_logged(self):
        import tools.http_retry as http_retry_mod
        _cfg(http_retry_attempts=2)
        logged = []
        orig_log = http_retry_mod.log_event
        http_retry_mod.log_event = lambda et, p: logged.append(et)

        def fn():
            raise requests.exceptions.ConnectionError("refused")

        try:
            with pytest.raises(requests.exceptions.ConnectionError):
                retry_request(fn, _sleep=self._no_sleep)
        finally:
            http_retry_mod.log_event = orig_log

        assert "http_retry" in logged


if __name__ == "__main__":
    import traceback
    tests = [
        TestIsTransient,
        TestRetryRequest,
    ]
    passed = failed = 0
    for cls in tests:
        obj = cls()
        for name in dir(cls):
            if not name.startswith("test_"):
                continue
            if hasattr(obj, "setup_method"):
                obj.setup_method()
            try:
                getattr(obj, name)()
                print(f"  PASS  {cls.__name__}.{name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {cls.__name__}.{name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
