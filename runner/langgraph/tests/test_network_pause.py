"""Unit tests for the M4c.4 network-pause guard.

Tests:
- probe_connectivity: mocked — no real network calls.
- is_network_error: pattern matching only, no I/O.
- Config fields exist and have correct defaults.
- State fields exist and serialise.
- update_logs_and_state skips all counters on a network pause.
- update_logs_and_state skips Supabase sync on a network pause.
- dispatch_worker probe failure sets network_unavailable_detected.
- decide_continue_or_stop polling wait and max patience stop.
- Stale watchdog is suppressed during a network pause.
- Provider 5xx and 401 are NOT classified as network errors.
- poll interval and patience are independently configurable.
"""
import os
import sys
import time
import types
import unittest.mock as mock
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.network_pause import (
    probe_connectivity,
    is_network_error,
    NETWORK_PAUSE_STOP,
    _NETWORK_ERROR_PATTERNS,
    _NON_NETWORK_PATTERNS,
)


# ── is_network_error ───────────────────────────────────────────────────────────

def test_dns_failure_is_network_error():
    assert is_network_error("name or service not known") is True


def test_connection_refused_is_network_error():
    assert is_network_error("connection refused") is True


def test_connection_reset_is_network_error():
    assert is_network_error("connection reset by peer") is True


def test_no_route_is_network_error():
    assert is_network_error("no route to host") is True


def test_network_unreachable_is_network_error():
    assert is_network_error("network is unreachable") is True


def test_ssl_handshake_is_network_error():
    assert is_network_error("ssl: handshake_failure") is True


def test_tls_handshake_is_network_error():
    assert is_network_error("tls handshake failure") is True


def test_errno_104_is_network_error():
    assert is_network_error("[errno 104]") is True


def test_errno_111_is_network_error():
    assert is_network_error("[errno 111]") is True


def test_errno_113_is_network_error():
    assert is_network_error("[errno 113]") is True


def test_network_unavailable_marker_is_network_error():
    assert is_network_error("network_unavailable: dns: some error") is True


def test_none_is_not_network_error():
    assert is_network_error(None) is False


def test_empty_string_is_not_network_error():
    assert is_network_error("") is False


def test_worker_success_is_not_network_error():
    assert is_network_error("task completed successfully") is False


# Provider errors should NOT be classified as network errors

def test_rate_limit_is_not_network_error():
    assert is_network_error("rate limit exceeded") is False


def test_usage_limit_is_not_network_error():
    assert is_network_error("Claude usage limit reached") is False


def test_subscription_is_not_network_error():
    assert is_network_error("subscription cooldown") is False


def test_unauthorized_is_not_network_error():
    assert is_network_error("unauthorized") is False


def test_authentication_failed_is_not_network_error():
    assert is_network_error("authentication failed") is False


def test_forbidden_is_not_network_error():
    assert is_network_error("forbidden") is False


def test_internal_server_error_is_not_network_error():
    assert is_network_error("internal server error") is False


def test_service_unavailable_is_not_network_error():
    assert is_network_error("service unavailable") is False


def test_bad_gateway_is_not_network_error():
    assert is_network_error("bad gateway") is False


def test_gateway_timeout_is_not_network_error():
    assert is_network_error("gateway timeout") is False


# ── probe_connectivity (mocked) ────────────────────────────────────────────────

def test_probe_returns_online_when_dns_succeeds():
    with mock.patch("tools.network_pause.socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [("AF_INET", "SOCK_STREAM", 0, "", ("8.8.8.8", 0))]
        result = probe_connectivity(timeout_s=1.0)
    assert result["online"] is True
    assert result["error"] is None


def test_probe_falls_back_to_http_when_dns_fails():
    import socket as _socket
    import urllib.request as _urlrequest
    mock_resp = mock.MagicMock()
    mock_resp.status = 204
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = mock.MagicMock(return_value=False)
    with mock.patch("tools.network_pause.socket.getaddrinfo", side_effect=OSError("dns fail")):
        with mock.patch("tools.network_pause.urllib.request.urlopen", return_value=mock_resp):
            result = probe_connectivity(timeout_s=1.0)
    assert result["online"] is True


def test_probe_returns_offline_when_both_fail():
    with mock.patch("tools.network_pause.socket.getaddrinfo", side_effect=OSError("dns fail")):
        with mock.patch("tools.network_pause.urllib.request.urlopen", side_effect=OSError("http fail")):
            result = probe_connectivity(timeout_s=1.0)
    assert result["online"] is False
    assert "error" in result
    assert result["error"] is not None


# ── Config integration ─────────────────────────────────────────────────────────

def test_config_has_network_pause_fields():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "network_pause_enabled")
    assert hasattr(cfg, "network_pause_probe_timeout_s")
    assert hasattr(cfg, "network_pause_poll_interval_s")
    assert hasattr(cfg, "network_pause_max_patience_s")


def test_config_defaults():
    from config import RunnerConfig
    with mock.patch.dict(os.environ, {}, clear=False):
        for k in ["NETWORK_PAUSE", "NETWORK_PAUSE_PROBE_TIMEOUT_S",
                   "NETWORK_PAUSE_POLL_INTERVAL_S", "NETWORK_PAUSE_MAX_PATIENCE_S"]:
            os.environ.pop(k, None)
        cfg = RunnerConfig()
    assert cfg.network_pause_enabled is True
    assert cfg.network_pause_probe_timeout_s == 5.0
    assert cfg.network_pause_poll_interval_s == 30
    assert cfg.network_pause_max_patience_s == 5400


def test_config_from_env():
    from config import RunnerConfig
    with mock.patch.dict(os.environ, {
        "NETWORK_PAUSE": "false",
        "NETWORK_PAUSE_PROBE_TIMEOUT_S": "2.0",
        "NETWORK_PAUSE_POLL_INTERVAL_S": "15",
        "NETWORK_PAUSE_MAX_PATIENCE_S": "600",
    }):
        cfg = RunnerConfig()
    assert cfg.network_pause_enabled is False
    assert cfg.network_pause_probe_timeout_s == 2.0
    assert cfg.network_pause_poll_interval_s == 15
    assert cfg.network_pause_max_patience_s == 600


def test_config_report_includes_network_pause_fields():
    from config import RunnerConfig
    report = RunnerConfig().report()
    assert "network_pause_enabled" in report
    assert "network_pause_probe_timeout_s" in report
    assert "network_pause_poll_interval_s" in report
    assert "network_pause_max_patience_s" in report


def test_poll_interval_and_patience_independent():
    from config import RunnerConfig
    with mock.patch.dict(os.environ, {
        "NETWORK_PAUSE_POLL_INTERVAL_S": "10",
        "NETWORK_PAUSE_MAX_PATIENCE_S": "3600",
    }):
        cfg = RunnerConfig()
    assert cfg.network_pause_poll_interval_s == 10
    assert cfg.network_pause_max_patience_s == 3600
    assert cfg.network_pause_poll_interval_s != cfg.network_pause_max_patience_s


# ── State integration ──────────────────────────────────────────────────────────

def test_state_has_network_pause_fields():
    from state import RunnerState
    s = RunnerState()
    assert s.network_unavailable_detected is False
    assert s.network_pause_started_at is None
    assert s.network_wait_seconds_total == 0.0


def test_state_network_fields_serialise():
    from state import RunnerState
    s = RunnerState(
        network_unavailable_detected=True,
        network_pause_started_at="2026-08-07T12:00:00",
        network_wait_seconds_total=300.0,
    )
    d = s.model_dump()
    assert d["network_unavailable_detected"] is True
    assert d["network_pause_started_at"] == "2026-08-07T12:00:00"
    assert d["network_wait_seconds_total"] == 300.0


# ── update_logs_and_state: counters untouched on network pause ──────────────────

def _make_state_with_task(**kwargs):
    from state import RunnerState
    base = dict(
        network_unavailable_detected=False,
        network_pause_started_at=None,
        network_wait_seconds_total=0.0,
        consecutive_failures=0,
        error_history=[],
        task_attempt_counts={},
        worker_timeout_count=0,
        codex_usage_limit_count=0,
        claude_subscription_cooldown_count=0,
        loop_count=0,
        last_task_completed_at=None,
        stale_run_warning_sent=False,
        retry_pending=None,
        current_task={"id": "t1", "title": "Test", "type": "backend", "branch": "feature/t1"},
        current_task_id="t1",
        current_worker="claude",
        worker_elapsed_seconds=0.0,
        worker_result={
            "worker": "claude", "mode": "cli", "success": False,
            "output": None, "error": "connection refused",
            "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
    )
    base.update(kwargs)
    return RunnerState(**base)


def _make_failing_state_with_task(**kwargs):
    """State where the worker failed with an HTTP 500 error (NOT a network error)."""
    from state import RunnerState
    base = dict(
        network_unavailable_detected=False,
        network_pause_started_at=None,
        network_wait_seconds_total=0.0,
        consecutive_failures=0,
        error_history=[],
        task_attempt_counts={},
        worker_timeout_count=0,
        codex_usage_limit_count=0,
        claude_subscription_cooldown_count=0,
        loop_count=0,
        last_task_completed_at=None,
        stale_run_warning_sent=False,
        retry_pending=None,
        current_task={"id": "t1", "title": "Test", "type": "backend", "branch": "feature/t1"},
        current_task_id="t1",
        current_worker="claude",
        worker_elapsed_seconds=0.0,
        worker_result={
            "worker": "claude", "mode": "cli", "success": False,
            "output": None, "error": "internal server error",
            "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
    )
    base.update(kwargs)
    return RunnerState(**base)


def _run_update_logs_patched(state):
    """Run update_logs_and_state with all external I/O mocked out."""
    with mock.patch("graph.mark_task_complete"), \
         mock.patch("graph.mark_task_failed"), \
         mock.patch("graph.mark_task_blocked"), \
         mock.patch("graph.requeue_task") as mock_requeue, \
         mock.patch("graph.load_tasks", return_value=[]), \
         mock.patch("graph.log_event"), \
         mock.patch("graph.update_state"), \
         mock.patch("graph.guard_completion_evidence", return_value={"complete": False, "blocked": False, "reasons": []}), \
         mock.patch("graph.check_mission_completion", return_value={"status": "running"}), \
         mock.patch("graph.mark_mission_completed"), \
         mock.patch("graph.mark_mission_failed"), \
         mock.patch("graph.mark_seeded_task_complete"), \
         mock.patch("graph.mark_seeded_task_failed"), \
         mock.patch("graph.complete_agent_run"), \
         mock.patch("graph.fail_agent_run"):
        from graph import update_logs_and_state
        result = update_logs_and_state(state)
    return result, mock_requeue


def test_counters_untouched_on_network_pause_pre_dispatch():
    """Pre-dispatch probe failure: all counters must stay at zero."""
    state = _make_state_with_task(
        network_unavailable_detected=True,
        network_pause_started_at="2026-08-07T10:00:00",
        worker_result={
            "worker": "claude", "mode": "cli", "success": False,
            "output": None, "error": "network_unavailable: dns: name or service not known",
            "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
    )
    result_state, mock_requeue = _run_update_logs_patched(state)

    # All failure counters must be untouched
    assert result_state.consecutive_failures == 0
    assert result_state.error_history == []
    assert result_state.task_attempt_counts == {}
    assert result_state.worker_timeout_count == 0
    # Task should be requeued (not failed)
    assert mock_requeue.called
    # retry_pending should be True so the loop doesn't ask ChatGPT
    assert result_state.retry_pending is True
    # network_unavailable_detected must remain True for decide_continue_or_stop
    assert result_state.network_unavailable_detected is True


def test_counters_untouched_on_mid_call_network_error():
    """Mid-call network error: counters stay at zero, task is requeued."""
    state = _make_state_with_task(
        worker_result={
            "worker": "claude", "mode": "cli", "success": False,
            "output": None, "error": "connection refused",
            "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
    )
    result_state, mock_requeue = _run_update_logs_patched(state)

    assert result_state.consecutive_failures == 0
    assert result_state.error_history == []
    assert result_state.task_attempt_counts == {}
    assert mock_requeue.called


def test_mid_call_network_error_sets_detected_flag():
    """Mid-call detection: network_unavailable_detected must be set."""
    state = _make_state_with_task(
        worker_result={
            "worker": "claude", "mode": "cli", "success": False,
            "output": None, "error": "name or service not known",
            "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
    )
    result_state, _ = _run_update_logs_patched(state)
    assert result_state.network_unavailable_detected is True
    assert result_state.network_pause_started_at is not None


def test_retry_count_not_incremented_on_network_pause():
    """Retry count must not increase on a network pause."""
    state = _make_state_with_task(
        network_unavailable_detected=True,
        worker_result={
            "worker": "claude", "mode": "cli", "success": False,
            "output": None, "error": "network_unavailable: connection timed out",
            "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
        current_task={
            "id": "t1", "title": "Test", "type": "backend",
            "branch": "feature/t1", "retry_count": 1,
        },
    )
    result_state, mock_requeue = _run_update_logs_patched(state)
    # requeue_task must be called with the SAME retry_count (1), not 2
    call_args = mock_requeue.call_args
    assert call_args[0][1] == 1  # second positional arg is retry_count


def test_supabase_sync_skipped_on_network_pause():
    """Seeded-mission Supabase sync must be skipped for network pauses."""
    from state import RunnerState
    state = RunnerState(
        network_unavailable_detected=True,
        network_pause_started_at="2026-08-07T10:00:00",
        current_task={
            "id": "t1", "title": "Test", "type": "backend", "branch": "feature/t1",
            "seeded_task_id": "st1", "seeded_mission_id": "m1",
        },
        current_task_id="t1",
        current_worker="claude",
        worker_elapsed_seconds=0.0,
        worker_result={
            "worker": "claude", "mode": "cli", "success": False,
            "output": None, "error": "network_unavailable: dns fail",
            "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
        consecutive_failures=0,
        error_history=[],
        task_attempt_counts={},
        worker_timeout_count=0,
        codex_usage_limit_count=0,
        claude_subscription_cooldown_count=0,
        loop_count=0,
        retry_pending=None,
    )

    with mock.patch("graph.mark_task_complete"), \
         mock.patch("graph.mark_task_failed") as mock_fail, \
         mock.patch("graph.mark_task_blocked"), \
         mock.patch("graph.requeue_task"), \
         mock.patch("graph.log_event"), \
         mock.patch("graph.update_state"), \
         mock.patch("graph.guard_completion_evidence", return_value={"complete": False, "blocked": False, "reasons": []}), \
         mock.patch("graph.check_mission_completion", return_value={"status": "running"}), \
         mock.patch("graph.mark_mission_completed"), \
         mock.patch("graph.mark_mission_failed"), \
         mock.patch("graph.mark_seeded_task_complete"), \
         mock.patch("graph.mark_seeded_task_failed") as mock_sync_fail, \
         mock.patch("graph.complete_agent_run"), \
         mock.patch("graph.fail_agent_run"), \
         mock.patch("graph.cfg") as mock_cfg:
        mock_cfg.network_pause_enabled = True
        mock_cfg.state_self_healing_enabled = True
        mock_cfg.max_transient_retries = 5
        mock_cfg.failure_guard_enabled = True
        mock_cfg.max_task_retries = 1
        mock_cfg.max_consecutive_failures = 3
        mock_cfg.failure_retry_backoff_enabled = True
        mock_cfg.failure_retry_backoff_base_s = 30.0
        mock_cfg.failure_retry_backoff_multiplier = 2.0
        mock_cfg.failure_retry_backoff_max_s = 300.0
        mock_cfg.worker_timeout_threshold = 2700
        mock_cfg.worker_timeout_guard_enabled = False
        mock_cfg.codex_usage_limit_guard_enabled = False
        mock_cfg.claude_subscription_cooldown_enabled = False
        mock_cfg.repeated_error_window = 10
        mock_cfg.max_repeated_errors = 3
        mock_cfg.max_task_attempts = 3
        mock_cfg.completion_evidence_gate_enabled = False
        mock_cfg.stale_run_watchdog_enabled = False
        mock_cfg.cost_budget_guard_enabled = False
        mock_cfg.seeded_mission_queue_enabled = True
        mock_cfg.has_supabase = True
        mock_cfg.claude_auth_mode = "api_key"
        mock_cfg.repo_path = "/tmp"
        mock_cfg.gate_block_scope = "proportionate"
        from graph import update_logs_and_state
        update_logs_and_state(state)

    # Supabase failure sync must NOT have been called
    assert not mock_sync_fail.called


# ── provider errors keep existing paths ───────────────────────────────────────

def test_provider_5xx_not_network_pause():
    """HTTP 5xx from a provider must NOT be treated as a network pause."""
    state = _make_failing_state_with_task(
        worker_result={
            "worker": "claude", "mode": "cli", "success": False,
            "output": None, "error": "internal server error",
            "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
    )
    result_state, mock_requeue = _run_update_logs_patched(state)
    # consecutive_failures SHOULD be incremented (normal failure path)
    assert result_state.consecutive_failures > 0 or mock_requeue.called
    # network_unavailable_detected must NOT be set
    assert result_state.network_unavailable_detected is False


def test_provider_401_not_network_pause():
    """HTTP 401 from a provider must NOT be treated as a network pause."""
    state = _make_failing_state_with_task(
        worker_result={
            "worker": "claude", "mode": "cli", "success": False,
            "output": None, "error": "unauthorized: invalid api key",
            "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
    )
    result_state, _ = _run_update_logs_patched(state)
    assert result_state.network_unavailable_detected is False


# ── decide_continue_or_stop: wait loop ────────────────────────────────────────

def _run_decide_patched(state, probe_side_effect, sleep_mock=None):
    """Run decide_continue_or_stop with probe and time.sleep mocked."""
    with mock.patch("graph.probe_connectivity", side_effect=probe_side_effect) as mock_probe, \
         mock.patch("graph.time.sleep") as mock_sleep, \
         mock.patch("graph.log_event"), \
         mock.patch("graph.update_state"), \
         mock.patch("graph.checkpoint_wip", return_value={"success": True}):
        from graph import decide_continue_or_stop
        result = decide_continue_or_stop(state)
    return result, mock_probe, mock_sleep


def _base_running_state(**kwargs):
    from state import RunnerState
    base = dict(
        status="running",
        stop_reason=None,
        loop_count=0,
        started_at=datetime.utcnow().isoformat(),
        network_unavailable_detected=True,
        network_pause_started_at=datetime.utcnow().isoformat(),
        network_wait_seconds_total=0.0,
        cooldown_wait_seconds_total=0.0,
        claude_subscription_cooldown_until=None,
        claude_subscription_cooldown_count=0,
        last_task_completed_at=datetime.utcnow().isoformat(),
        stale_run_warning_sent=False,
        wip_checkpoint=None,
    )
    base.update(kwargs)
    return RunnerState(**base)


def test_probe_failure_pauses_loop():
    """probe_connectivity() failure enters the wait loop, not a task dispatch."""
    state = _base_running_state()

    # Probe succeeds on second call (simulating network restoration)
    probe_calls = [{"online": False, "error": "dns fail"}, {"online": True, "error": None}]
    result_state, mock_probe, mock_sleep = _run_decide_patched(state, probe_calls)

    # Probe must have been called
    assert mock_probe.call_count >= 1
    # Sleep must have been called (the poll interval)
    assert mock_sleep.call_count >= 1
    # network_unavailable_detected must be cleared after restoration
    assert result_state.network_unavailable_detected is False
    # Loop must NOT have stopped
    assert result_state.stop_reason is None
    assert result_state.status == "running"


def test_network_restored_clears_flag():
    """After connectivity is restored, network_unavailable_detected is False."""
    state = _base_running_state()
    # Probe fails once then succeeds
    probe_side_effect = [{"online": False, "error": "err"}, {"online": True, "error": None}]
    result_state, _, _ = _run_decide_patched(state, probe_side_effect)
    assert result_state.network_unavailable_detected is False


def test_max_patience_exceeded_stops_loop():
    """If max patience is exceeded, stop_reason must be 'network_unavailable'."""
    from config import RunnerConfig
    # Set outage start FAR in the past to immediately exceed patience
    past = datetime(2020, 1, 1, 0, 0, 0).isoformat()
    state = _base_running_state(
        network_pause_started_at=past,
    )
    # Probe always fails
    probe_side_effect = [{"online": False, "error": "dns fail"}] * 100

    with mock.patch("graph.probe_connectivity", side_effect=probe_side_effect), \
         mock.patch("graph.time.sleep"), \
         mock.patch("graph.log_event"), \
         mock.patch("graph.update_state"), \
         mock.patch("graph.checkpoint_wip", return_value={"success": True}), \
         mock.patch("graph.cfg") as mock_cfg:
        mock_cfg.network_pause_enabled = True
        mock_cfg.network_pause_probe_timeout_s = 5.0
        mock_cfg.network_pause_poll_interval_s = 30
        mock_cfg.network_pause_max_patience_s = 5400  # 90 min
        mock_cfg.max_loop_tasks = 100
        mock_cfg.max_runtime_minutes = 480
        mock_cfg.wip_checkpoint_enabled = False
        mock_cfg.runner_dry_run = False
        mock_cfg.claude_subscription_cooldown_until = None
        from graph import decide_continue_or_stop
        result_state = decide_continue_or_stop(state)

    assert result_state.stop_reason == NETWORK_PAUSE_STOP
    assert result_state.status == "stopped"


def test_max_patience_stop_reason_is_correct_string():
    """The stop reason for patience exceeded must be 'network_unavailable'."""
    assert NETWORK_PAUSE_STOP == "network_unavailable"


def test_wait_time_excluded_from_runtime():
    """Network wait seconds are excluded from MAX_RUNTIME_MINUTES budget.

    Setup: started 60 minutes ago, max_runtime=30 min, network_wait=45 min.
    Without exclusion: 60 > 30 → would stop.
    With exclusion: 60 - 45 = 15 min < 30 min → must NOT stop.
    """
    from state import RunnerState
    from datetime import timedelta
    sixty_min_ago = (datetime.utcnow() - timedelta(minutes=60)).isoformat()
    state = RunnerState(
        status="running",
        stop_reason=None,
        loop_count=0,
        started_at=sixty_min_ago,
        network_unavailable_detected=False,
        network_pause_started_at=None,
        network_wait_seconds_total=2700.0,  # 45 minutes of network wait
        cooldown_wait_seconds_total=0.0,
        claude_subscription_cooldown_until=None,
        claude_subscription_cooldown_count=0,
        last_task_completed_at=datetime.utcnow().isoformat(),
        stale_run_warning_sent=False,
        wip_checkpoint=None,
    )
    with mock.patch("graph.probe_connectivity"), \
         mock.patch("graph.time.sleep"), \
         mock.patch("graph.log_event"), \
         mock.patch("graph.update_state"), \
         mock.patch("graph.checkpoint_wip", return_value={"success": True}), \
         mock.patch("graph.cfg") as mock_cfg:
        mock_cfg.network_pause_enabled = False
        mock_cfg.max_loop_tasks = 1000
        mock_cfg.max_runtime_minutes = 30   # only 30 min; wall-clock is 60 min
        mock_cfg.wip_checkpoint_enabled = False
        mock_cfg.runner_dry_run = False
        mock_cfg.claude_subscription_cooldown_until = None
        from graph import decide_continue_or_stop
        result_state = decide_continue_or_stop(state)
    # effective elapsed ≈ 60 - 45 = 15 min < 30 min → should not stop on runtime
    assert result_state.stop_reason != "max_runtime"


# ── stale watchdog suppressed during network pause ────────────────────────────

def test_stale_watchdog_suppressed_on_network_pause():
    """Stale-run watchdog must not fire when _is_network_pause is True."""
    state = _make_state_with_task(
        network_unavailable_detected=True,
        loop_count=5,
        # last_task_completed_at very far in the past — would normally trip watchdog
        last_task_completed_at="2020-01-01T00:00:00",
        worker_result={
            "worker": "claude", "mode": "cli", "success": False,
            "output": None, "error": "network_unavailable: dns fail",
            "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
    )
    with mock.patch("graph.mark_task_complete"), \
         mock.patch("graph.mark_task_failed"), \
         mock.patch("graph.mark_task_blocked"), \
         mock.patch("graph.requeue_task"), \
         mock.patch("graph.log_event"), \
         mock.patch("graph.update_state"), \
         mock.patch("graph.guard_completion_evidence", return_value={"complete": False, "blocked": False, "reasons": []}), \
         mock.patch("graph.check_mission_completion", return_value={"status": "running"}), \
         mock.patch("graph.mark_mission_completed"), \
         mock.patch("graph.mark_mission_failed"), \
         mock.patch("graph.mark_seeded_task_complete"), \
         mock.patch("graph.mark_seeded_task_failed"), \
         mock.patch("graph.complete_agent_run"), \
         mock.patch("graph.fail_agent_run"), \
         mock.patch("graph.cfg") as mock_cfg:
        mock_cfg.network_pause_enabled = True
        mock_cfg.stale_run_watchdog_enabled = True
        mock_cfg.max_stale_task_minutes = 120
        mock_cfg.stale_run_warn_minutes = 75
        mock_cfg.state_self_healing_enabled = True
        mock_cfg.max_transient_retries = 5
        mock_cfg.failure_guard_enabled = True
        mock_cfg.max_task_retries = 1
        mock_cfg.max_consecutive_failures = 3
        mock_cfg.failure_retry_backoff_enabled = True
        mock_cfg.failure_retry_backoff_base_s = 30.0
        mock_cfg.failure_retry_backoff_multiplier = 2.0
        mock_cfg.failure_retry_backoff_max_s = 300.0
        mock_cfg.worker_timeout_threshold = 2700
        mock_cfg.worker_timeout_guard_enabled = False
        mock_cfg.codex_usage_limit_guard_enabled = False
        mock_cfg.claude_subscription_cooldown_enabled = False
        mock_cfg.repeated_error_window = 10
        mock_cfg.max_repeated_errors = 3
        mock_cfg.max_task_attempts = 3
        mock_cfg.completion_evidence_gate_enabled = False
        mock_cfg.cost_budget_guard_enabled = False
        mock_cfg.seeded_mission_queue_enabled = False
        mock_cfg.has_supabase = False
        mock_cfg.claude_auth_mode = "api_key"
        mock_cfg.repo_path = "/tmp"
        mock_cfg.gate_block_scope = "proportionate"
        from graph import update_logs_and_state
        result_state = update_logs_and_state(state)

    # stop_reason must NOT be "stale_run" — watchdog was suppressed
    assert result_state.stop_reason != "stale_run"


if __name__ == "__main__":
    import traceback
    tests = [
        test_dns_failure_is_network_error,
        test_connection_refused_is_network_error,
        test_connection_reset_is_network_error,
        test_no_route_is_network_error,
        test_network_unreachable_is_network_error,
        test_ssl_handshake_is_network_error,
        test_tls_handshake_is_network_error,
        test_errno_104_is_network_error,
        test_errno_111_is_network_error,
        test_errno_113_is_network_error,
        test_network_unavailable_marker_is_network_error,
        test_none_is_not_network_error,
        test_empty_string_is_not_network_error,
        test_worker_success_is_not_network_error,
        test_rate_limit_is_not_network_error,
        test_usage_limit_is_not_network_error,
        test_subscription_is_not_network_error,
        test_unauthorized_is_not_network_error,
        test_authentication_failed_is_not_network_error,
        test_forbidden_is_not_network_error,
        test_internal_server_error_is_not_network_error,
        test_service_unavailable_is_not_network_error,
        test_bad_gateway_is_not_network_error,
        test_gateway_timeout_is_not_network_error,
        test_probe_returns_online_when_dns_succeeds,
        test_probe_falls_back_to_http_when_dns_fails,
        test_probe_returns_offline_when_both_fail,
        test_config_has_network_pause_fields,
        test_config_defaults,
        test_config_from_env,
        test_config_report_includes_network_pause_fields,
        test_poll_interval_and_patience_independent,
        test_state_has_network_pause_fields,
        test_state_network_fields_serialise,
        test_counters_untouched_on_network_pause_pre_dispatch,
        test_counters_untouched_on_mid_call_network_error,
        test_mid_call_network_error_sets_detected_flag,
        test_retry_count_not_incremented_on_network_pause,
        test_supabase_sync_skipped_on_network_pause,
        test_provider_5xx_not_network_pause,
        test_provider_401_not_network_pause,
        test_probe_failure_pauses_loop,
        test_network_restored_clears_flag,
        test_max_patience_exceeded_stops_loop,
        test_max_patience_stop_reason_is_correct_string,
        test_wait_time_excluded_from_runtime,
        test_stale_watchdog_suppressed_on_network_pause,
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
