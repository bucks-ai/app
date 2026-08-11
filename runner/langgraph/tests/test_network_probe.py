"""Unit tests for tools/network_probe.py (M4c.4).

All tests are pure — no real DNS lookups, no real HTTP calls, no subprocess.
The probe_fn injectable is used throughout.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.network_probe import probe_connectivity, is_network_error_string


# ---------------------------------------------------------------------------
# probe_connectivity — injectable probe_fn
# ---------------------------------------------------------------------------

def _fn_online(_timeout):
    return {"dns_ok": True, "http_ok": True}


def _fn_offline(_timeout):
    return {"dns_ok": False, "http_ok": False}


def _fn_dns_only(_timeout):
    return {"dns_ok": True, "http_ok": False}


def _fn_http_only(_timeout):
    return {"dns_ok": False, "http_ok": True}


def test_probe_online_returns_online():
    r = probe_connectivity(probe_fn=_fn_online)
    assert r["online"] is True
    assert r["dns_ok"] is True
    assert r["http_ok"] is True


def test_probe_offline_returns_offline():
    r = probe_connectivity(probe_fn=_fn_offline)
    assert r["online"] is False
    assert r["dns_ok"] is False
    assert r["http_ok"] is False


def test_probe_dns_only_is_online():
    r = probe_connectivity(probe_fn=_fn_dns_only)
    assert r["online"] is True
    assert r["dns_ok"] is True
    assert r["http_ok"] is False


def test_probe_http_only_is_online():
    r = probe_connectivity(probe_fn=_fn_http_only)
    assert r["online"] is True
    assert r["dns_ok"] is False
    assert r["http_ok"] is True


def test_probe_result_has_required_keys():
    r = probe_connectivity(probe_fn=_fn_offline)
    assert "online" in r
    assert "detail" in r
    assert "dns_ok" in r
    assert "http_ok" in r


def test_probe_detail_is_string():
    r = probe_connectivity(probe_fn=_fn_online)
    assert isinstance(r["detail"], str)


def test_probe_passes_timeout_to_probe_fn():
    received = []

    def _fn(timeout):
        received.append(timeout)
        return {"dns_ok": True, "http_ok": False}

    probe_connectivity(timeout_s=7.5, probe_fn=_fn)
    assert received == [7.5]


# ---------------------------------------------------------------------------
# is_network_error_string — DNS, connection, timeout patterns
# ---------------------------------------------------------------------------

def test_dns_failure_is_network():
    assert is_network_error_string("gaierror: [Errno -2] Name or service not known")


def test_dns_resolution_failure_is_network():
    assert is_network_error_string("Temporary failure in name resolution")


def test_nodename_is_network():
    assert is_network_error_string("nodename nor servname provided")


def test_getaddrinfo_is_network():
    assert is_network_error_string("getaddrinfo failed")


def test_connection_refused_is_network():
    assert is_network_error_string("ConnectionRefusedError: [Errno 111] Connection refused")


def test_connection_reset_is_network():
    assert is_network_error_string("Connection reset by peer")


def test_no_route_to_host_is_network():
    assert is_network_error_string("No route to host")


def test_network_unreachable_is_network():
    assert is_network_error_string("Network is unreachable")


def test_tls_handshake_is_network():
    assert is_network_error_string("ssl handshake failed: TLSV1_ALERT_INTERNAL_ERROR")


def test_connect_timeout_is_network():
    assert is_network_error_string("Connect timeout on endpoint")


def test_read_timeout_is_network():
    assert is_network_error_string("ReadTimeout: HTTPSConnectionPool(host='api.anthropic.com')")


def test_operation_timed_out_is_network():
    assert is_network_error_string("Operation timed out after 5000 milliseconds")


def test_etimedout_is_network():
    assert is_network_error_string("OSError: [Errno 110] ETIMEDOUT")


def test_broken_pipe_is_network():
    assert is_network_error_string("BrokenPipeError: [Errno 32] Broken pipe")


def test_remote_end_closed_is_network():
    assert is_network_error_string("Remote end closed connection without response")


def test_eof_violation_is_network():
    assert is_network_error_string("EOF occurred in violation of protocol")


def test_urlerror_is_network():
    assert is_network_error_string("URLError: <urlopen error connection timed out>")


# ---------------------------------------------------------------------------
# is_network_error_string — provider errors that are NOT network loss
# ---------------------------------------------------------------------------

def test_rate_limit_429_not_network():
    assert not is_network_error_string("HTTP Error 429: Too Many Requests")


def test_rate_limit_text_not_network():
    assert not is_network_error_string("rate limit exceeded, please slow down")


def test_too_many_requests_not_network():
    assert not is_network_error_string("too many requests from this IP")


def test_401_not_network():
    assert not is_network_error_string("HTTP 401 unauthorized")


def test_403_not_network():
    assert not is_network_error_string("403 Forbidden — authentication failed")


def test_500_not_network():
    assert not is_network_error_string("HTTP 500 Internal Server Error")


def test_503_not_network():
    assert not is_network_error_string("503 Service Unavailable")


def test_bad_gateway_not_network():
    assert not is_network_error_string("502 Bad Gateway")


def test_empty_string_not_network():
    assert not is_network_error_string("")


def test_none_not_network():
    assert not is_network_error_string(None)


def test_generic_error_not_network():
    assert not is_network_error_string("ValueError: invalid literal for int()")


def test_task_failure_not_network():
    assert not is_network_error_string("AssertionError: expected 42 but got 0")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    tests = [
        test_probe_online_returns_online,
        test_probe_offline_returns_offline,
        test_probe_dns_only_is_online,
        test_probe_http_only_is_online,
        test_probe_result_has_required_keys,
        test_probe_detail_is_string,
        test_probe_passes_timeout_to_probe_fn,
        test_dns_failure_is_network,
        test_dns_resolution_failure_is_network,
        test_nodename_is_network,
        test_getaddrinfo_is_network,
        test_connection_refused_is_network,
        test_connection_reset_is_network,
        test_no_route_to_host_is_network,
        test_network_unreachable_is_network,
        test_tls_handshake_is_network,
        test_connect_timeout_is_network,
        test_read_timeout_is_network,
        test_operation_timed_out_is_network,
        test_etimedout_is_network,
        test_broken_pipe_is_network,
        test_remote_end_closed_is_network,
        test_eof_violation_is_network,
        test_urlerror_is_network,
        test_rate_limit_429_not_network,
        test_rate_limit_text_not_network,
        test_too_many_requests_not_network,
        test_401_not_network,
        test_403_not_network,
        test_500_not_network,
        test_503_not_network,
        test_bad_gateway_not_network,
        test_empty_string_not_network,
        test_none_not_network,
        test_generic_error_not_network,
        test_task_failure_not_network,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {t.__name__}: {exc}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
