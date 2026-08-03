"""Unit tests for M4c.0's credential-authority fix in the resource gate.

Runs standalone (no pytest dependency):

    python tests/test_gate_credential_authority.py

The runner's own config/env is the authority on whether a credential exists.
Before this fix the gate trusted the worker's self-report, so during M2 and M4b
it repeatedly halted the entire run asking a human to provision VERCEL_TOKEN and
VERCEL_PROJECT_ID that were sitting in .env the whole time.

Also covers the per-task state reset that skip-and-continue depends on: with the
loop no longer stopping at a task-scoped block, a stale verdict from the
previous task must never route the next one straight back out of the graph.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.resource_gate import (
    available_credential_names,
    collect_requests,
    env_names_in,
    evaluate_gate,
    filter_satisfied_credentials,
)
import graph
from state import RunnerState

# Captured per-test — see the note in test_gate_authority.py on why the stub
# is not installed at import time.
_EVENTS = []


# ---------------------------------------------------------------------------
# env_names_in — only env-var-shaped tokens count
# ---------------------------------------------------------------------------

def test_extracts_env_var_names():
    assert env_names_in("VERCEL_TOKEN") == ["VERCEL_TOKEN"]
    assert env_names_in("VERCEL_TOKEN (for preview deploys)") == ["VERCEL_TOKEN"]
    assert env_names_in("vercel_token") == ["VERCEL_TOKEN"], "lower-case still matches"


def test_prose_without_an_env_var_matches_nothing():
    assert env_names_in("a Vercel token") == []
    assert env_names_in("access to the Stripe dashboard") == []
    assert env_names_in("") == []


def test_extracts_several_names_from_one_line():
    assert env_names_in("VERCEL_TOKEN and VERCEL_PROJECT_ID") == [
        "VERCEL_TOKEN", "VERCEL_PROJECT_ID",
    ]


# ---------------------------------------------------------------------------
# filter_satisfied_credentials
# ---------------------------------------------------------------------------

def test_the_m2_m4b_regression_credentials_are_filtered_out():
    """The exact case that repeatedly halted M2 and M4b."""
    r = filter_satisfied_credentials(
        ["VERCEL_TOKEN", "VERCEL_PROJECT_ID"],
        {"VERCEL_TOKEN", "VERCEL_PROJECT_ID"},
    )
    assert r["missing"] == [], r
    assert r["satisfied"] == ["VERCEL_TOKEN", "VERCEL_PROJECT_ID"], r


def test_genuinely_missing_credentials_still_block():
    r = filter_satisfied_credentials(["STRIPE_API_KEY"], {"VERCEL_TOKEN"})
    assert r["missing"] == ["STRIPE_API_KEY"], r
    assert r["satisfied"] == [], r


def test_a_line_naming_several_is_satisfied_only_when_all_are_present():
    r = filter_satisfied_credentials(
        ["VERCEL_TOKEN and VERCEL_PROJECT_ID"], {"VERCEL_TOKEN"},
    )
    assert r["missing"] == ["VERCEL_TOKEN and VERCEL_PROJECT_ID"], r


def test_non_env_var_requests_are_never_auto_satisfied():
    """A human-shaped ask can't be answered by an env var, so it must survive."""
    r = filter_satisfied_credentials(
        ["access to the Stripe dashboard"], {"STRIPE_API_KEY", "ACCESS"},
    )
    assert r["missing"] == ["access to the Stripe dashboard"], r


def test_no_available_set_filters_nothing():
    r = filter_satisfied_credentials(["VERCEL_TOKEN"], None)
    assert r["missing"] == ["VERCEL_TOKEN"] and r["satisfied"] == [], r


# ---------------------------------------------------------------------------
# available_credential_names — names only, never values
# ---------------------------------------------------------------------------

def test_collects_names_from_env():
    names = available_credential_names(environ={"VERCEL_TOKEN": "secret-value"})
    assert "VERCEL_TOKEN" in names
    assert "secret-value" not in names, "values must never be collected"


def test_ignores_empty_and_whitespace_values():
    names = available_credential_names(environ={"A_KEY": "", "B_KEY": "   ", "C_KEY": "x"})
    assert names == {"C_KEY"}, names


def test_collects_names_from_config_fields():
    from config import RunnerConfig

    cfg = RunnerConfig()
    cfg.vercel_token = "set-somehow"
    names = available_credential_names(environ={}, config=cfg)
    assert "VERCEL_TOKEN" in names, "config fields map onto their env-var spelling"


# ---------------------------------------------------------------------------
# collect_requests / evaluate_gate wiring
# ---------------------------------------------------------------------------

def test_collect_moves_satisfied_out_of_all():
    req = collect_requests(
        {"credentials_needed": ["VERCEL_TOKEN", "STRIPE_API_KEY"], "resources_needed": []},
        available={"VERCEL_TOKEN"},
    )
    assert req["credentials"] == ["STRIPE_API_KEY"], req
    assert req["all"] == ["STRIPE_API_KEY"], req
    assert req["satisfied"] == ["VERCEL_TOKEN"], req


def test_gate_does_not_block_when_every_credential_is_present():
    gate = evaluate_gate(
        {"credentials_needed": ["VERCEL_TOKEN", "VERCEL_PROJECT_ID"]},
        provided=False,
        available={"VERCEL_TOKEN", "VERCEL_PROJECT_ID"},
    )
    assert gate["blocked"] is False and gate["status"] == "none", gate


def test_resources_are_not_filtered_by_env():
    """Resources are access/services, not env vars — env presence can't satisfy them."""
    gate = evaluate_gate(
        {"resources_needed": ["SUPABASE_URL project access"]},
        provided=False,
        available={"SUPABASE_URL"},
    )
    assert gate["blocked"] is True, gate


# ---------------------------------------------------------------------------
# Node behaviour
# ---------------------------------------------------------------------------

def _state(summary):
    return RunnerState(
        current_task_id="t1",
        current_task={"id": "t1", "title": "demo"},
        worker_result={"success": False},
        worker_summary=summary,
    )


def _with_temp_runner_dir(fn):
    original_dir = graph._RUNNER_DIR
    original_block = graph.mark_task_blocked
    original_cfg_token = graph.cfg.vercel_token
    original_log, original_state = graph.log_event, graph.update_state
    blocked = []
    graph.mark_task_blocked = lambda task_id, reason: blocked.append((task_id, reason))
    graph.log_event = lambda event, payload=None, **k: _EVENTS.append((event, payload or {}))
    graph.update_state = lambda *a, **k: None
    _EVENTS.clear()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "outbox").mkdir()
        (root / "inbox").mkdir()
        graph._RUNNER_DIR = root
        try:
            return fn(root / "outbox", root / "inbox", blocked)
        finally:
            graph._RUNNER_DIR = original_dir
            graph.mark_task_blocked = original_block
            graph.cfg.vercel_token = original_cfg_token
            graph.log_event, graph.update_state = original_log, original_state


def test_node_does_not_request_a_credential_the_runner_already_has():
    def body(outbox, inbox, blocked):
        graph.cfg.resource_gate_enabled = True
        graph.cfg.vercel_token = "already-configured"
        out = graph.request_resources_if_needed(_state({"credentials_needed": ["VERCEL_TOKEN"]}))
        assert out.resource_request_status is None, out.resource_request_status
        assert out.stop_reason is None, out.stop_reason
        assert list(outbox.iterdir()) == [], "no human request for a credential we hold"
        assert blocked == [], blocked
        names = [e for e, _ in _EVENTS]
        assert "resource_request_already_satisfied" in names, names
    _with_temp_runner_dir(body)


def test_node_still_requests_the_credentials_that_are_missing():
    def body(outbox, inbox, blocked):
        graph.cfg.resource_gate_enabled = True
        graph.cfg.vercel_token = "already-configured"
        out = graph.request_resources_if_needed(_state(
            {"credentials_needed": ["VERCEL_TOKEN", "STRIPE_API_KEY"]},
        ))
        assert out.resource_request_status == "pending", out.resource_request_status
        text = (outbox / "t1_resource_request.txt").read_text()
        assert "STRIPE_API_KEY" in text
        assert "VERCEL_TOKEN" not in text, "already provisioned; must not be asked for"
        assert "already-configured" not in text, "never a secret value"
    _with_temp_runner_dir(body)


def test_node_block_records_the_authority_it_consulted():
    def body(outbox, inbox, blocked):
        graph.cfg.resource_gate_enabled = True
        graph.request_resources_if_needed(_state({"credentials_needed": ["STRIPE_API_KEY"]}))
        waiting = [p for e, p in _EVENTS if e == "resource_request_waiting"]
        assert waiting, [e for e, _ in _EVENTS]
        assert waiting[0]["authority"] == "runner_config_env", waiting[0]
        assert waiting[0]["block_scope"] == "task", waiting[0]
    _with_temp_runner_dir(body)


# ---------------------------------------------------------------------------
# Per-task state reset — the invariant skip-and-continue depends on
# ---------------------------------------------------------------------------

def test_reset_clears_the_previous_tasks_verdicts():
    state = RunnerState(
        resource_request_status="pending",
        acceptance_criteria_status="failed",
        definition_of_done_status="failed",
        code_review_status="failed",
        high_risk_review_status="failed",
        merge_approval_status="pending",
        merge_risk_level="high",
        sql_approval_status="pending",
        check_passed=False,
        auto_repair_attempt=2,
    )
    graph._reset_task_scoped_state(state)
    for field_name in graph._TASK_SCOPED_STATE_DEFAULTS:
        assert getattr(state, field_name) == graph._TASK_SCOPED_STATE_DEFAULTS[field_name], field_name


def test_reset_leaves_session_counters_alone():
    state = RunnerState(
        loop_count=4,
        session_cost=12.5,
        gate_skipped_task_count=2,
        worker_timeout_count=1,
        strategic_tasks_since_gate=3,
        consecutive_failures=2,
    )
    graph._reset_task_scoped_state(state)
    assert state.loop_count == 4
    assert state.session_cost == 12.5
    assert state.gate_skipped_task_count == 2
    assert state.worker_timeout_count == 1
    assert state.strategic_tasks_since_gate == 3
    assert state.consecutive_failures == 2


def test_a_blocked_task_does_not_route_the_next_one_out_of_the_graph():
    """Without the reset, task A's pending resource block would send every
    later task straight to decide_continue_or_stop, dispatching no worker."""
    state = RunnerState(resource_request_status="pending")
    assert graph._route_after_resource_gate(state) == "decide_continue_or_stop"
    graph._reset_task_scoped_state(state)
    assert graph._route_after_resource_gate(state) == "run_checks_if_needed"
    assert graph._route_after_business_repo(state) == "check_acceptance_criteria"


def test_business_repo_route_stops_on_a_task_scoped_resource_block():
    """A task-scoped block leaves stop_reason clear, but the task still has no
    repo — it must not fall through to worker dispatch."""
    state = RunnerState(resource_request_status="pending")
    assert graph._route_after_business_repo(state) == "decide_continue_or_stop"


if __name__ == "__main__":
    tests = [
        test_extracts_env_var_names,
        test_prose_without_an_env_var_matches_nothing,
        test_extracts_several_names_from_one_line,
        test_the_m2_m4b_regression_credentials_are_filtered_out,
        test_genuinely_missing_credentials_still_block,
        test_a_line_naming_several_is_satisfied_only_when_all_are_present,
        test_non_env_var_requests_are_never_auto_satisfied,
        test_no_available_set_filters_nothing,
        test_collects_names_from_env,
        test_ignores_empty_and_whitespace_values,
        test_collects_names_from_config_fields,
        test_collect_moves_satisfied_out_of_all,
        test_gate_does_not_block_when_every_credential_is_present,
        test_resources_are_not_filtered_by_env,
        test_node_does_not_request_a_credential_the_runner_already_has,
        test_node_still_requests_the_credentials_that_are_missing,
        test_node_block_records_the_authority_it_consulted,
        test_reset_clears_the_previous_tasks_verdicts,
        test_reset_leaves_session_counters_alone,
        test_a_blocked_task_does_not_route_the_next_one_out_of_the_graph,
        test_business_repo_route_stops_on_a_task_scoped_resource_block,
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
