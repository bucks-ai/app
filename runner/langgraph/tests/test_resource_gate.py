"""Unit tests for the resource & credential request gate.

Runs standalone (no pytest dependency), mirroring test_deploy_node.py:

    python tests/test_resource_gate.py

Covers the pure decision helpers in tools/resource_gate.py and the
graph.request_resources_if_needed node. The node is exercised against a
temporary outbox/inbox so no real disk state under the runner is touched, and
log_event / update_state / mark_task_blocked are stubbed.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.resource_gate import collect_requests, evaluate_gate, format_request_file
from tools.summary_tools import parse_worker_summary
import graph
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Pure helpers: collect_requests / evaluate_gate / format_request_file
# ---------------------------------------------------------------------------

def test_collect_filters_placeholders():
    summary = {"credentials_needed": ["STRIPE_API_KEY", "none"], "resources_needed": ["(none)", "Postgres access"]}
    req = collect_requests(summary)
    assert req["credentials"] == ["STRIPE_API_KEY"], req
    assert req["resources"] == ["Postgres access"], req
    assert req["all"] == ["STRIPE_API_KEY", "Postgres access"], req


def test_collect_handles_empty_summary():
    assert collect_requests(None)["all"] == []
    assert collect_requests({})["all"] == []


def test_evaluate_none_when_nothing_requested():
    gate = evaluate_gate({"credentials_needed": ["none"]}, provided=False)
    assert gate["status"] == "none" and gate["blocked"] is False, gate


def test_evaluate_pending_blocks():
    gate = evaluate_gate({"credentials_needed": ["STRIPE_API_KEY"]}, provided=False)
    assert gate["blocked"] is True and gate["status"] == "pending", gate


def test_evaluate_fulfilled_does_not_block():
    gate = evaluate_gate({"credentials_needed": ["STRIPE_API_KEY"]}, provided=True)
    assert gate["blocked"] is False and gate["status"] == "fulfilled", gate


def test_format_request_lists_items_and_no_values():
    req = collect_requests({"credentials_needed": ["STRIPE_API_KEY"], "resources_needed": ["S3 bucket"]})
    text = format_request_file("t1", "Wire up payments", req, "t1_resources_provided.txt")
    assert "STRIPE_API_KEY" in text
    assert "S3 bucket" in text
    assert "t1_resources_provided.txt" in text
    assert "Do NOT paste secret values" in text


# ---------------------------------------------------------------------------
# Summary parsing wires the new fields through
# ---------------------------------------------------------------------------

NEEDS_SUMMARY = """
- Files Created: (none)
- Files Modified:
  - lib/pay.ts
- Check Result: fail
- Credentials Needed:
  - STRIPE_API_KEY
- Resources Needed:
  - Stripe account access
- Known Limitations:
  - blocked on missing key
- Next Task: (none)
"""


def test_summary_parses_needs():
    s = parse_worker_summary(NEEDS_SUMMARY)
    assert s["credentials_needed"] == ["STRIPE_API_KEY"], s["credentials_needed"]
    assert s["resources_needed"] == ["Stripe account access"], s["resources_needed"]


def test_summary_inline_none_is_empty():
    s = parse_worker_summary("- Credentials Needed: none\n- Resources Needed: (none)\n")
    assert s["credentials_needed"] == []
    assert s["resources_needed"] == []


# ---------------------------------------------------------------------------
# Node behavior — exercised against a temp outbox/inbox
# ---------------------------------------------------------------------------

def _state(summary):
    return RunnerState(
        current_task_id="t1",
        current_task={"id": "t1", "title": "demo"},
        worker_result={"success": False},
        worker_summary=summary,
    )


def _with_temp_runner_dir(fn):
    """Run fn(outbox, inbox) with graph._RUNNER_DIR pointed at a temp dir."""
    original = graph._RUNNER_DIR
    blocked_calls = []
    original_block = graph.mark_task_blocked
    graph.mark_task_blocked = lambda task_id, reason: blocked_calls.append((task_id, reason))
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "outbox").mkdir()
        (root / "inbox").mkdir()
        graph._RUNNER_DIR = root
        try:
            return fn(root / "outbox", root / "inbox", blocked_calls)
        finally:
            graph._RUNNER_DIR = original
            graph.mark_task_blocked = original_block


def test_node_blocks_and_writes_request_when_needs_unfulfilled():
    def body(outbox, inbox, blocked):
        graph.cfg.resource_gate_enabled = True
        out = graph.request_resources_if_needed(_state({"credentials_needed": ["STRIPE_API_KEY"]}))
        assert out.resource_request_status == "pending", out.resource_request_status
        assert out.stop_reason == "awaiting_resources", out.stop_reason
        req_file = outbox / "t1_resource_request.txt"
        assert req_file.exists(), "request should be written to outbox"
        assert "STRIPE_API_KEY" in req_file.read_text()
        assert blocked == [("t1", "awaiting resources/credentials")], blocked
    _with_temp_runner_dir(body)


def test_node_proceeds_when_no_needs():
    def body(outbox, inbox, blocked):
        graph.cfg.resource_gate_enabled = True
        out = graph.request_resources_if_needed(_state({"credentials_needed": ["none"]}))
        assert out.resource_request_status is None, out.resource_request_status
        assert out.stop_reason is None, out.stop_reason
        assert list(outbox.iterdir()) == [], "no request file when nothing needed"
        assert blocked == []
    _with_temp_runner_dir(body)


def test_node_fulfilled_when_inbox_file_present():
    def body(outbox, inbox, blocked):
        graph.cfg.resource_gate_enabled = True
        (inbox / "t1_resources_provided.txt").write_text("ok")
        out = graph.request_resources_if_needed(_state({"credentials_needed": ["STRIPE_API_KEY"]}))
        assert out.resource_request_status == "fulfilled", out.resource_request_status
        assert out.stop_reason is None, out.stop_reason
        assert blocked == [], "fulfilled path must not mark the task blocked"
    _with_temp_runner_dir(body)


def test_node_bypassed_when_gate_disabled():
    def body(outbox, inbox, blocked):
        graph.cfg.resource_gate_enabled = False
        try:
            out = graph.request_resources_if_needed(_state({"credentials_needed": ["STRIPE_API_KEY"]}))
            assert out.stop_reason is None, out.stop_reason
            assert list(outbox.iterdir()) == [], "disabled gate writes nothing"
        finally:
            graph.cfg.resource_gate_enabled = True
    _with_temp_runner_dir(body)


# ---------------------------------------------------------------------------
# Routing + wiring
# ---------------------------------------------------------------------------

def test_route_blocks_to_decide():
    s = RunnerState(resource_request_status="pending")
    assert graph._route_after_resource_gate(s) == "decide_continue_or_stop"


def test_route_proceeds_to_checks():
    s = RunnerState(resource_request_status="fulfilled")
    assert graph._route_after_resource_gate(s) == "run_checks_if_needed"
    assert graph._route_after_resource_gate(RunnerState()) == "run_checks_if_needed"


def test_node_is_wired_into_graph():
    nodes = list(graph.build_graph().get_graph().nodes)
    assert "request_resources_if_needed" in nodes, nodes


if __name__ == "__main__":
    tests = [
        test_collect_filters_placeholders,
        test_collect_handles_empty_summary,
        test_evaluate_none_when_nothing_requested,
        test_evaluate_pending_blocks,
        test_evaluate_fulfilled_does_not_block,
        test_format_request_lists_items_and_no_values,
        test_summary_parses_needs,
        test_summary_inline_none_is_empty,
        test_node_blocks_and_writes_request_when_needs_unfulfilled,
        test_node_proceeds_when_no_needs,
        test_node_fulfilled_when_inbox_file_present,
        test_node_bypassed_when_gate_disabled,
        test_route_blocks_to_decide,
        test_route_proceeds_to_checks,
        test_node_is_wired_into_graph,
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
