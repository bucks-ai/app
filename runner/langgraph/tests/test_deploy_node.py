"""Unit tests for the graph.deploy_if_needed node.

Runs standalone (no pytest dependency), mirroring test_vercel_polling.py:

    python tests/test_deploy_node.py

The node is exercised in isolation: trigger_deploy, log_event and state
persistence are stubbed so no network or disk I/O happens.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# A token may be needed for has_vercel; the real network is never hit because
# trigger_deploy is always stubbed below.
os.environ.setdefault("VERCEL_TOKEN", "test-token")

import graph
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


def _landed_state():
    """A state where the worker succeeded, checks passed, and a commit landed."""
    return RunnerState(
        current_task_id="t1",
        current_task={"id": "t1", "title": "demo", "issue_number": None},
        worker_result={"success": True},
        check_passed=True,
        last_commit="abc1234",
    )


def _stub_trigger(verdict, calls):
    def _trigger(project_name=None, project_id=None, poll=True):
        calls.append({"project_name": project_name, "project_id": project_id})
        return verdict
    return _trigger


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_deploy_runs_when_changes_landed():
    calls = []
    verdict = {"success": True, "poll": {"ready": True, "state": "READY", "polls": 2}}
    graph.trigger_deploy = _stub_trigger(verdict, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_token = "test-token"

    state = graph.deploy_if_needed(_landed_state())

    assert len(calls) == 1, f"expected one deploy, got {len(calls)}"
    assert state.deploy_result == verdict
    assert state.deploy_ready is True
    assert state.last_completed_step == "deploy_if_needed"


def test_deploy_passes_configured_project_id():
    calls = []
    graph.trigger_deploy = _stub_trigger({"success": True, "poll": {}}, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_token = "test-token"
    graph.cfg.vercel_project_id = "prj_123"

    graph.deploy_if_needed(_landed_state())

    assert calls[0]["project_id"] == "prj_123", calls


def test_deploy_failure_marks_not_ready():
    calls = []
    verdict = {"success": False, "poll": {"ready": False, "state": "ERROR", "timed_out": False}}
    graph.trigger_deploy = _stub_trigger(verdict, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_token = "test-token"

    state = graph.deploy_if_needed(_landed_state())

    assert state.deploy_ready is False
    assert state.deploy_result["poll"]["state"] == "ERROR"


# ---------------------------------------------------------------------------
# Skip paths — trigger_deploy must NOT be called
# ---------------------------------------------------------------------------

def test_skips_when_no_commit():
    calls = []
    graph.trigger_deploy = _stub_trigger({"success": True}, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_token = "test-token"

    state = _landed_state()
    state.last_commit = None
    out = graph.deploy_if_needed(state)

    assert calls == [], "deploy should be skipped when no commit landed"
    assert out.deploy_result is None


def test_skips_when_check_failed():
    calls = []
    graph.trigger_deploy = _stub_trigger({"success": True}, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_token = "test-token"

    state = _landed_state()
    state.check_passed = False
    out = graph.deploy_if_needed(state)

    assert calls == [], "deploy should be skipped when checks failed"
    assert out.deploy_result is None


def test_skips_when_worker_failed():
    calls = []
    graph.trigger_deploy = _stub_trigger({"success": True}, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_token = "test-token"

    state = _landed_state()
    state.worker_result = {"success": False}
    out = graph.deploy_if_needed(state)

    assert calls == [], "deploy should be skipped when the worker failed"
    assert out.deploy_result is None


def test_skips_when_auto_deploy_off():
    calls = []
    graph.trigger_deploy = _stub_trigger({"success": True}, calls)
    graph.cfg.auto_deploy = False
    graph.cfg.vercel_token = "test-token"

    out = graph.deploy_if_needed(_landed_state())

    assert calls == [], "deploy should be skipped when AUTO_DEPLOY is off"
    assert out.deploy_result is None


def test_skips_when_no_vercel_token():
    calls = []
    graph.trigger_deploy = _stub_trigger({"success": True}, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_token = None

    out = graph.deploy_if_needed(_landed_state())

    assert calls == [], "deploy should be skipped without a VERCEL_TOKEN"
    assert out.deploy_result is None


# ---------------------------------------------------------------------------
# Wiring — the node sits between apply_sql_if_needed and update_github_if_needed
# ---------------------------------------------------------------------------

def test_deploy_node_is_wired_into_graph():
    nodes = list(graph.build_graph().get_graph().nodes)
    assert "deploy_if_needed" in nodes, nodes


if __name__ == "__main__":
    tests = [
        test_deploy_runs_when_changes_landed,
        test_deploy_passes_configured_project_id,
        test_deploy_failure_marks_not_ready,
        test_skips_when_no_commit,
        test_skips_when_check_failed,
        test_skips_when_worker_failed,
        test_skips_when_auto_deploy_off,
        test_skips_when_no_vercel_token,
        test_deploy_node_is_wired_into_graph,
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
