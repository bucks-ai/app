"""A subscription cooldown must never accumulate toward the repeated-error ceiling.

Regression origin — 2026-08-03, task m4c0-05. The cooldown guard worked
perfectly twice (detected -> slept 1800s -> resumed), but each cooldown ALSO
produced a `worker returned no output` failure that the repeated-error guard
counted. On the third one:

    18:39:41.241  loop_blocked_on_repeated_error   match_count: 3
    18:39:41.364  claude_subscription_cooldown_detected   cooldown_count: 3
    18:39:41.516  loop_stopped   reason: repeated_errors

The repeated-error guard runs ~120ms BEFORE the cooldown evaluation in
`update_logs_and_state`, so it set `stop_reason` first and the cooldown guard's
"just sleep it off" decision arrived too late to matter. Net effect: the loop
died on rate limits it was explicitly designed to wait out.

These tests pin: cooldown-shaped failures are exempt from the repeated-error
guard and from error_history; genuine repeated errors still block; the
exemption applies only in subscription mode with the Claude worker.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import graph
from state import RunnerState

COOLDOWN_OUTPUT = (
    '{"is_error":true,"api_error_status":429,'
    '"result":"You\'ve hit your session limit · resets 4am (America/New_York)"}'
)


class _Cfg:
    """Only the fields update_logs_and_state touches for these paths."""
    claude_subscription_cooldown_enabled = True
    claude_auth_mode = "subscription"
    max_repeated_errors = 3
    repeated_error_window = 10
    claude_subscription_cooldown_wait_s = 1800
    claude_subscription_cooldown_max_waits = 0

    def __getattr__(self, name):  # every other guard disabled / neutral
        if name.endswith("_enabled") or name.endswith("_guard_enabled"):
            return False
        return 0


def _run(monkeypatch, *, error, output, worker="claude", auth_mode="subscription", history_len=2):
    cfg = _Cfg()
    cfg.claude_auth_mode = auth_mode
    monkeypatch.setattr(graph, "cfg", cfg, raising=False)
    monkeypatch.setattr(graph, "mark_task_failed", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(graph, "requeue_task", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(graph, "_persist", lambda s, *a, **k: s, raising=False)

    state = RunnerState()
    state.current_task = {"id": "t1", "title": "t"}
    state.current_task_id = "t1"
    state.worker_result = {"success": False, "error": error, "output": output, "worker": worker}
    # Pre-load the history so one more identical error would trip the ceiling.
    state.error_history = [{"error": error, "task_id": "t1"} for _ in range(history_len)]
    return graph.update_logs_and_state(state)


def test_cooldown_failure_does_not_trip_repeated_error_guard(monkeypatch):
    state = _run(monkeypatch, error="worker returned no output", output=COOLDOWN_OUTPUT)
    assert state.stop_reason != "repeated_errors", state.stop_reason


def test_cooldown_failure_is_not_appended_to_error_history(monkeypatch):
    state = _run(monkeypatch, error="worker returned no output", output=COOLDOWN_OUTPUT)
    assert len(state.error_history) == 2, state.error_history


def test_genuine_repeated_error_still_blocks(monkeypatch):
    state = _run(monkeypatch, error="ImportError: no module named foo", output="traceback...")
    assert state.stop_reason == "repeated_errors", state.stop_reason


def test_exemption_does_not_apply_in_api_key_mode(monkeypatch):
    state = _run(
        monkeypatch, error="worker returned no output",
        output=COOLDOWN_OUTPUT, auth_mode="api_key",
    )
    assert state.stop_reason == "repeated_errors", state.stop_reason


def test_exemption_does_not_apply_to_other_workers(monkeypatch):
    state = _run(
        monkeypatch, error="worker returned no output",
        output=COOLDOWN_OUTPUT, worker="codex",
    )
    assert state.stop_reason == "repeated_errors", state.stop_reason
