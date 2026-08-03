"""Unit tests for the gate authority registry and proportionality policy (M4c.0).

Runs standalone (no pytest dependency), mirroring test_resource_gate.py:

    python tests/test_gate_authority.py

Covers the pure helpers in tools/gate_authority.py and the graph-level
`_record_gate_block` behaviour: a task-scoped gate sets the task aside without
stopping the run, a loop-scoped gate still halts, and every block records which
authority it consulted.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.gate_authority import (
    GATE_REGISTRY,
    POLICY_LOOP,
    POLICY_PROPORTIONATE,
    SCOPE_LOOP,
    SCOPE_TASK,
    _REQUIRED_KEYS,
    authority_payload,
    evaluate_gate_block,
    gate_authority,
    normalize_policy,
)
import graph
from state import RunnerState

# Flight-recorder events captured per-test. The stub is installed inside the
# fixture rather than at import time: pytest imports every test module before
# running anything, so a module-level `graph.log_event = ...` is silently
# replaced by whichever test module happens to be imported last.
_EVENTS = []


# ---------------------------------------------------------------------------
# Registry integrity
# ---------------------------------------------------------------------------

def test_every_entry_is_well_formed():
    for gate, entry in GATE_REGISTRY.items():
        assert _REQUIRED_KEYS <= set(entry), f"{gate} missing {_REQUIRED_KEYS - set(entry)}"
        assert entry["scope"] in (SCOPE_TASK, SCOPE_LOOP), gate
        assert entry["assesses"] in ("task", "run"), gate
        assert isinstance(entry["external"], bool), gate
        assert isinstance(entry["destructive"], bool), gate
        assert entry["rationale"].strip(), f"{gate} needs a rationale"


def test_run_level_gates_are_loop_scoped():
    """A gate is only allowed a loop-wide halt if it judges the run itself."""
    for gate, entry in GATE_REGISTRY.items():
        if entry["scope"] == SCOPE_LOOP:
            assert entry["assesses"] == "run", (
                f"{gate} halts the whole loop but only assesses one task"
            )


def test_task_level_gates_default_to_skip_and_continue():
    for gate, entry in GATE_REGISTRY.items():
        if entry["assesses"] == "task":
            assert entry["scope"] == SCOPE_TASK, gate
            assert evaluate_gate_block(gate)["halt_loop"] is False, gate


def test_the_motivating_gates_are_registered():
    """Every gate named in the M4c.0 audit must have an entry."""
    for gate in (
        "merge_approval", "pr_checks", "sql_approval", "resource_credential",
        "acceptance_criteria", "definition_of_done", "independent_code_review",
        "high_risk_review", "strategic", "cost_budget_session",
        "cost_budget_task", "worker_timeout", "stale_run",
    ):
        assert gate_authority(gate)["known"] is True, gate


def test_unknown_gate_falls_back_to_conservative_halt():
    descriptor = gate_authority("not_a_real_gate")
    assert descriptor["known"] is False
    assert evaluate_gate_block("not_a_real_gate")["halt_loop"] is True


# ---------------------------------------------------------------------------
# evaluate_gate_block
# ---------------------------------------------------------------------------

def test_task_scoped_gate_does_not_halt():
    d = evaluate_gate_block("acceptance_criteria")
    assert d["scope"] == SCOPE_TASK and d["halt_loop"] is False, d


def test_loop_scoped_gate_halts():
    d = evaluate_gate_block("stale_run")
    assert d["scope"] == SCOPE_LOOP and d["halt_loop"] is True, d


def test_systemic_escalates_a_task_scoped_gate():
    d = evaluate_gate_block("merge_approval", systemic=True)
    assert d["halt_loop"] is True, d


def test_legacy_policy_restores_loop_wide_halts():
    for gate in GATE_REGISTRY:
        assert evaluate_gate_block(gate, policy=POLICY_LOOP)["halt_loop"] is True, gate


def test_destructive_gates_are_never_downgraded():
    """Scope is only ever widened, so no policy can turn a destructive gate's
    block into a skip."""
    for gate, entry in GATE_REGISTRY.items():
        if not entry["destructive"]:
            continue
        for policy in (POLICY_PROPORTIONATE, POLICY_LOOP):
            for systemic in (False, True):
                scope = evaluate_gate_block(gate, systemic=systemic, policy=policy)["scope"]
                if entry["scope"] == SCOPE_LOOP:
                    assert scope == SCOPE_LOOP, (gate, policy, systemic)
                else:
                    assert scope in (SCOPE_TASK, SCOPE_LOOP), (gate, policy, systemic)


def test_session_spend_cap_still_blocks_but_task_cap_does_not():
    assert evaluate_gate_block("cost_budget_session")["halt_loop"] is True
    assert evaluate_gate_block("cost_budget_task")["halt_loop"] is False


# ---------------------------------------------------------------------------
# authority_payload — every block records who it consulted
# ---------------------------------------------------------------------------

def test_payload_names_the_authority():
    p = authority_payload("pr_checks", sha="abc")
    assert p["gate"] == "pr_checks"
    assert p["authority"] == "github_branch_protection"
    assert p["authority_external"] is True
    assert p["sha"] == "abc"


def test_block_payload_carries_scope_and_policy():
    p = evaluate_gate_block("resource_credential")["payload"]
    assert p["authority"] == "runner_config_env"
    assert p["block_scope"] == SCOPE_TASK
    assert p["gate_block_policy"] == POLICY_PROPORTIONATE


def test_normalize_policy_rejects_junk():
    assert normalize_policy("loop") == POLICY_LOOP
    assert normalize_policy("  LOOP ") == POLICY_LOOP
    assert normalize_policy("proportionate") == POLICY_PROPORTIONATE
    assert normalize_policy(None) == POLICY_PROPORTIONATE
    assert normalize_policy("nonsense") == POLICY_PROPORTIONATE


# ---------------------------------------------------------------------------
# graph._record_gate_block
# ---------------------------------------------------------------------------

def _with_policy(policy, fn):
    original_policy = graph.cfg.gate_block_scope
    original_log, original_state = graph.log_event, graph.update_state
    graph.cfg.gate_block_scope = policy
    graph.log_event = lambda event, payload=None, **k: _EVENTS.append((event, payload or {}))
    graph.update_state = lambda *a, **k: None
    _EVENTS.clear()
    try:
        return fn()
    finally:
        graph.cfg.gate_block_scope = original_policy
        graph.log_event, graph.update_state = original_log, original_state


def test_record_task_scoped_block_leaves_loop_running():
    def body():
        state = RunnerState(current_task_id="t1", loop_count=3)
        graph._record_gate_block(
            state, "acceptance_criteria",
            event="gate_blocked", payload={"task_id": "t1"},
            stop_reason="missing_acceptance_criteria", task_id="t1",
        )
        assert state.stop_reason is None, state.stop_reason
        assert state.gate_skipped_task_count == 1
        # Counted as a loop so MAX_LOOP_TASKS still bounds a run of skips.
        assert state.loop_count == 4, state.loop_count
        assert state.last_task_completed_at is not None
        names = [e for e, _ in _EVENTS]
        assert "gate_blocked" in names and "gate_block_task_scoped" in names, names
    _with_policy(POLICY_PROPORTIONATE, body)


def test_record_loop_scoped_block_sets_stop_reason():
    def body():
        state = RunnerState(current_task_id="t1", loop_count=3)
        graph._record_gate_block(
            state, "stale_run",
            event="loop_blocked_on_stale_run", payload={},
            stop_reason="stale_run", task_id="t1", pre_completion=False,
        )
        assert state.stop_reason == "stale_run"
        assert state.gate_skipped_task_count == 0
        assert state.loop_count == 3, "a halt must not fabricate a loop"
    _with_policy(POLICY_PROPORTIONATE, body)


def test_record_block_logs_the_authority_consulted():
    def body():
        state = RunnerState(current_task_id="t1")
        graph._record_gate_block(
            state, "merge_approval",
            event="merge_approval_required", payload={"risk_level": "high"},
            stop_reason="awaiting_merge_approval", task_id="t1",
        )
        payload = dict(_EVENTS[0][1])
        assert payload["authority"] == "human_approval_file", payload
        assert payload["authority_external"] is True
        assert payload["block_scope"] == SCOPE_TASK
        assert payload["risk_level"] == "high", "caller payload must survive"
    _with_policy(POLICY_PROPORTIONATE, body)


def test_legacy_policy_makes_every_block_halt_the_loop():
    def body():
        state = RunnerState(current_task_id="t1", loop_count=3)
        graph._record_gate_block(
            state, "acceptance_criteria",
            event="gate_blocked", payload={}, stop_reason="missing_acceptance_criteria",
            task_id="t1",
        )
        assert state.stop_reason == "missing_acceptance_criteria"
        assert state.loop_count == 3
    _with_policy(POLICY_LOOP, body)


def test_record_block_does_not_clobber_an_existing_stop_reason():
    def body():
        state = RunnerState(current_task_id="t1", stop_reason="max_runtime")
        graph._record_gate_block(
            state, "stale_run", event="loop_blocked_on_stale_run", payload={},
            stop_reason="stale_run", task_id="t1", pre_completion=False,
        )
        assert state.stop_reason == "max_runtime"
    _with_policy(POLICY_PROPORTIONATE, body)


if __name__ == "__main__":
    tests = [
        test_every_entry_is_well_formed,
        test_run_level_gates_are_loop_scoped,
        test_task_level_gates_default_to_skip_and_continue,
        test_the_motivating_gates_are_registered,
        test_unknown_gate_falls_back_to_conservative_halt,
        test_task_scoped_gate_does_not_halt,
        test_loop_scoped_gate_halts,
        test_systemic_escalates_a_task_scoped_gate,
        test_legacy_policy_restores_loop_wide_halts,
        test_destructive_gates_are_never_downgraded,
        test_session_spend_cap_still_blocks_but_task_cap_does_not,
        test_payload_names_the_authority,
        test_block_payload_carries_scope_and_policy,
        test_normalize_policy_rejects_junk,
        test_record_task_scoped_block_leaves_loop_running,
        test_record_loop_scoped_block_sets_stop_reason,
        test_record_block_logs_the_authority_consulted,
        test_legacy_policy_makes_every_block_halt_the_loop,
        test_record_block_does_not_clobber_an_existing_stop_reason,
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
