"""Unit tests for vercel_tools deployment polling.

Runs standalone (no pytest dependency), mirroring test_summary_tools.py:

    python tests/test_vercel_polling.py

The poll loop takes injectable ``fetch`` / ``sleep`` / ``now`` callables so it can
be driven deterministically without the Vercel API or real time.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# A token must be present for has_vercel; the real network is never hit because
# every test injects its own ``fetch``.
os.environ.setdefault("VERCEL_TOKEN", "test-token")

import tools.vercel_tools as vt
from config import get_config

# Keep the flight recorder clean during tests.
vt.log_event = lambda *a, **k: None


class FakeClock:
    """Monotonic clock that only advances when sleep() is called."""

    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


def _seq_fetch(states):
    """Return a fetch() that yields one deployment per call from ``states``.

    Each entry is either a readyState string or a full result dict. After the
    list is exhausted the last state repeats.
    """
    calls = {"i": 0}

    def fetch():
        i = min(calls["i"], len(states) - 1)
        calls["i"] += 1
        entry = states[i]
        if isinstance(entry, dict):
            return entry
        return {"available": True, "deployment": {"readyState": entry}}

    return fetch


# ---------------------------------------------------------------------------
# normalize_ready_state / is_terminal_state
# ---------------------------------------------------------------------------

def test_normalize_reads_readystate():
    assert vt.normalize_ready_state({"readyState": "building"}) == "BUILDING"


def test_normalize_reads_state_fallback():
    assert vt.normalize_ready_state({"state": "ready"}) == "READY"


def test_normalize_unknown_for_empty():
    assert vt.normalize_ready_state(None) == "UNKNOWN"
    assert vt.normalize_ready_state({}) == "UNKNOWN"


def test_is_terminal():
    assert vt.is_terminal_state("READY") is True
    assert vt.is_terminal_state("ERROR") is True
    assert vt.is_terminal_state("CANCELED") is True
    assert vt.is_terminal_state("BUILDING") is False
    assert vt.is_terminal_state("QUEUED") is False
    assert vt.is_terminal_state("") is False


# ---------------------------------------------------------------------------
# poll_deployment_until_terminal
# ---------------------------------------------------------------------------

def test_poll_reaches_ready():
    clock = FakeClock()
    res = vt.poll_deployment_until_terminal(
        deployment_id="dpl_1",
        timeout=180,
        interval=5,
        fetch=_seq_fetch(["QUEUED", "BUILDING", "READY"]),
        sleep=clock.sleep,
        now=clock.now,
    )
    assert res["ready"] is True, res
    assert res["terminal"] is True, res
    assert res["timed_out"] is False, res
    assert res["state"] == "READY", res
    assert res["polls"] == 3, res


def test_poll_detects_failure():
    clock = FakeClock()
    res = vt.poll_deployment_until_terminal(
        deployment_id="dpl_2",
        timeout=180,
        interval=5,
        fetch=_seq_fetch(["BUILDING", "ERROR"]),
        sleep=clock.sleep,
        now=clock.now,
    )
    assert res["ready"] is False, res
    assert res["terminal"] is True, res
    assert res["timed_out"] is False, res
    assert res["state"] == "ERROR", res


def test_poll_detects_canceled():
    clock = FakeClock()
    res = vt.poll_deployment_until_terminal(
        deployment_id="dpl_3",
        timeout=180,
        interval=5,
        fetch=_seq_fetch(["CANCELED"]),
        sleep=clock.sleep,
        now=clock.now,
    )
    assert res["terminal"] is True and res["ready"] is False, res
    assert res["polls"] == 1, res


def test_poll_times_out():
    clock = FakeClock()
    res = vt.poll_deployment_until_terminal(
        deployment_id="dpl_4",
        timeout=10,
        interval=5,
        fetch=_seq_fetch(["BUILDING"]),  # never terminal
        sleep=clock.sleep,
        now=clock.now,
    )
    assert res["timed_out"] is True, res
    assert res["terminal"] is False, res
    assert res["ready"] is False, res
    assert res["state"] == "BUILDING", res
    # timeout=10, interval=5 → poll at t=0 and t=5, then give up before t=10.
    assert res["polls"] == 2, res


def test_poll_stops_on_unavailable():
    clock = FakeClock()
    res = vt.poll_deployment_until_terminal(
        deployment_id="dpl_5",
        timeout=180,
        interval=5,
        fetch=_seq_fetch([{"available": False, "error": "boom"}]),
        sleep=clock.sleep,
        now=clock.now,
    )
    assert res["available"] is False, res
    assert res["ready"] is False, res
    assert res["error"] == "boom", res
    assert res["polls"] == 1, res


def test_poll_no_token():
    cfg = get_config()
    saved = cfg.vercel_token
    cfg.vercel_token = None
    try:
        res = vt.poll_deployment_until_terminal(deployment_id="dpl_6")
        assert res["available"] is False, res
        assert res["reason"] == "no VERCEL_TOKEN", res
        assert res["polls"] == 0, res
    finally:
        cfg.vercel_token = saved


def test_poll_uses_config_defaults():
    cfg = get_config()
    saved_t, saved_i = cfg.vercel_poll_timeout, cfg.vercel_poll_interval
    cfg.vercel_poll_timeout = 10
    cfg.vercel_poll_interval = 5
    clock = FakeClock()
    try:
        res = vt.poll_deployment_until_terminal(
            deployment_id="dpl_7",
            fetch=_seq_fetch(["BUILDING"]),
            sleep=clock.sleep,
            now=clock.now,
        )
        assert res["timed_out"] is True, res
        assert res["polls"] == 2, res
    finally:
        cfg.vercel_poll_timeout = saved_t
        cfg.vercel_poll_interval = saved_i


# ---------------------------------------------------------------------------
# trigger_deploy integration (polling path, no network)
# ---------------------------------------------------------------------------

def test_trigger_deploy_polls_and_reports_ready(monkeypatched=None):
    cfg = get_config()
    saved_status = vt.get_deployment_status
    saved_poll = vt.poll_deployment_until_terminal
    saved_auto = cfg.auto_deploy
    saved_pollcfg = cfg.auto_deploy_poll
    cfg.auto_deploy = True
    cfg.auto_deploy_poll = True
    vt.get_deployment_status = lambda project_id=None: {
        "available": True,
        "latest": {"uid": "dpl_x", "readyState": "BUILDING"},
    }
    vt.poll_deployment_until_terminal = lambda **kw: {
        "available": True, "ready": True, "terminal": True, "timed_out": False,
        "state": "READY", "polls": 2,
    }
    try:
        res = vt.trigger_deploy(project_name="bucks-ai")
        assert res["success"] is True, res
        assert res["poll"]["ready"] is True, res
    finally:
        vt.get_deployment_status = saved_status
        vt.poll_deployment_until_terminal = saved_poll
        cfg.auto_deploy = saved_auto
        cfg.auto_deploy_poll = saved_pollcfg


def test_trigger_deploy_failure_marks_unsuccessful():
    cfg = get_config()
    saved_status = vt.get_deployment_status
    saved_poll = vt.poll_deployment_until_terminal
    saved_auto = cfg.auto_deploy
    saved_pollcfg = cfg.auto_deploy_poll
    cfg.auto_deploy = True
    cfg.auto_deploy_poll = True
    vt.get_deployment_status = lambda project_id=None: {
        "available": True,
        "latest": {"uid": "dpl_y", "readyState": "BUILDING"},
    }
    vt.poll_deployment_until_terminal = lambda **kw: {
        "available": True, "ready": False, "terminal": True, "timed_out": False,
        "state": "ERROR", "polls": 1,
    }
    try:
        res = vt.trigger_deploy(project_name="bucks-ai")
        assert res["success"] is False, res
        assert res["poll"]["state"] == "ERROR", res
    finally:
        vt.get_deployment_status = saved_status
        vt.poll_deployment_until_terminal = saved_poll
        cfg.auto_deploy = saved_auto
        cfg.auto_deploy_poll = saved_pollcfg


def test_trigger_deploy_skips_poll_when_disabled():
    cfg = get_config()
    saved_status = vt.get_deployment_status
    saved_auto = cfg.auto_deploy
    saved_pollcfg = cfg.auto_deploy_poll
    cfg.auto_deploy = True
    cfg.auto_deploy_poll = False
    vt.get_deployment_status = lambda project_id=None: {
        "available": True, "latest": {"uid": "dpl_z", "readyState": "BUILDING"},
    }
    try:
        res = vt.trigger_deploy(project_name="bucks-ai")
        assert "poll" not in res, res
        assert res["success"] is True, res  # available snapshot, no poll
    finally:
        vt.get_deployment_status = saved_status
        cfg.auto_deploy = saved_auto
        cfg.auto_deploy_poll = saved_pollcfg


# ---------------------------------------------------------------------------
# normalize_deployment_url
# ---------------------------------------------------------------------------

def test_normalize_deployment_url_adds_https():
    assert vt.normalize_deployment_url("my-app.vercel.app") == "https://my-app.vercel.app"


def test_normalize_deployment_url_passes_through_absolute():
    assert vt.normalize_deployment_url("http://my-app.vercel.app") == "http://my-app.vercel.app"
    assert vt.normalize_deployment_url("https://my-app.vercel.app") == "https://my-app.vercel.app"


def test_normalize_deployment_url_none_for_empty():
    assert vt.normalize_deployment_url(None) is None
    assert vt.normalize_deployment_url("") is None


# ---------------------------------------------------------------------------
# trigger_deploy — url plumbing
# ---------------------------------------------------------------------------

def test_trigger_deploy_sets_url_from_snapshot_when_poll_disabled():
    cfg = get_config()
    saved_status = vt.get_deployment_status
    saved_auto = cfg.auto_deploy
    saved_pollcfg = cfg.auto_deploy_poll
    cfg.auto_deploy = True
    cfg.auto_deploy_poll = False
    vt.get_deployment_status = lambda project_id=None: {
        "available": True, "latest": {"uid": "dpl_z", "url": "my-app.vercel.app"},
    }
    try:
        res = vt.trigger_deploy(project_name="bucks-ai")
        assert res["url"] == "https://my-app.vercel.app", res
    finally:
        vt.get_deployment_status = saved_status
        cfg.auto_deploy = saved_auto
        cfg.auto_deploy_poll = saved_pollcfg


def test_trigger_deploy_prefers_polled_deployment_url():
    cfg = get_config()
    saved_status = vt.get_deployment_status
    saved_poll = vt.poll_deployment_until_terminal
    saved_auto = cfg.auto_deploy
    saved_pollcfg = cfg.auto_deploy_poll
    cfg.auto_deploy = True
    cfg.auto_deploy_poll = True
    vt.get_deployment_status = lambda project_id=None: {
        "available": True,
        "latest": {"uid": "dpl_x", "url": "dpl-x-preview.vercel.app"},
    }
    vt.poll_deployment_until_terminal = lambda **kw: {
        "available": True, "ready": True, "terminal": True, "timed_out": False,
        "state": "READY", "polls": 2,
        "deployment": {"uid": "dpl_x", "url": "my-app.vercel.app"},
    }
    try:
        res = vt.trigger_deploy(project_name="bucks-ai")
        assert res["url"] == "https://my-app.vercel.app", res
    finally:
        vt.get_deployment_status = saved_status
        vt.poll_deployment_until_terminal = saved_poll
        cfg.auto_deploy = saved_auto
        cfg.auto_deploy_poll = saved_pollcfg


def test_trigger_deploy_keeps_snapshot_url_when_poll_omits_deployment():
    cfg = get_config()
    saved_status = vt.get_deployment_status
    saved_poll = vt.poll_deployment_until_terminal
    saved_auto = cfg.auto_deploy
    saved_pollcfg = cfg.auto_deploy_poll
    cfg.auto_deploy = True
    cfg.auto_deploy_poll = True
    vt.get_deployment_status = lambda project_id=None: {
        "available": True,
        "latest": {"uid": "dpl_x", "url": "my-app.vercel.app"},
    }
    vt.poll_deployment_until_terminal = lambda **kw: {
        "available": True, "ready": True, "terminal": True, "timed_out": False,
        "state": "READY", "polls": 2,
    }
    try:
        res = vt.trigger_deploy(project_name="bucks-ai")
        assert res["url"] == "https://my-app.vercel.app", res
    finally:
        vt.get_deployment_status = saved_status
        vt.poll_deployment_until_terminal = saved_poll
        cfg.auto_deploy = saved_auto
        cfg.auto_deploy_poll = saved_pollcfg


if __name__ == "__main__":
    import traceback

    tests = [
        test_normalize_reads_readystate,
        test_normalize_reads_state_fallback,
        test_normalize_unknown_for_empty,
        test_is_terminal,
        test_poll_reaches_ready,
        test_poll_detects_failure,
        test_poll_detects_canceled,
        test_poll_times_out,
        test_poll_stops_on_unavailable,
        test_poll_no_token,
        test_poll_uses_config_defaults,
        test_trigger_deploy_polls_and_reports_ready,
        test_trigger_deploy_failure_marks_unsuccessful,
        test_trigger_deploy_skips_poll_when_disabled,
        test_normalize_deployment_url_adds_https,
        test_normalize_deployment_url_passes_through_absolute,
        test_normalize_deployment_url_none_for_empty,
        test_trigger_deploy_sets_url_from_snapshot_when_poll_disabled,
        test_trigger_deploy_prefers_polled_deployment_url,
        test_trigger_deploy_keeps_snapshot_url_when_poll_omits_deployment,
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
