"""Tests for tools/stop_diagnostics.py — the loop-stop diagnostics registry.

The load-bearing test here is ``TestRegistryCoverage``: it scans ``graph.py``
and ``tools/*.py`` for every stop reason the runner can set and fails when one
has no handler. That is what makes diagnostics non-optional — a new stop reason
cannot ship without a written cause and fix.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import tools.stop_diagnostics as sd
from tools.stop_diagnostics import (
    ANOMALOUS,
    EXPECTED,
    EXPECTED_STOP_REASONS,
    STOP_HANDLERS,
    STOP_REPORT_EVENT,
    STOP_REPORT_FILENAME,
    UNSPECIFIED_STOP,
    build_stop_diagnostics,
    classify_stop,
    collect_config_values,
    collect_evidence,
    collect_recent_events,
    env_name_for,
    format_slack_message,
    format_stop_report,
    get_handler,
    is_secret_key,
    report_loop_stop,
    unhandled_stop_reasons,
)

_RUNNER_DIR = os.path.join(os.path.dirname(__file__), "..")
_TOOLS_DIR = os.path.join(_RUNNER_DIR, "tools")


# ---------------------------------------------------------------------------
# Source scanning — how a new stop reason gets caught
# ---------------------------------------------------------------------------

# `state.stop_reason = "x"` and the `stop_reason="x"` keyword passed to
# _record_gate_block.
_ASSIGNED = re.compile(r'stop_reason\s*=\s*"([a-z0-9_]+)"')
# `reason = "deploy_timed_out" if timed_out else "deploy_failed"` — assigned to
# stop_reason one line later, so the direct pattern above misses it.
_TERNARY = re.compile(r'\breason\s*=\s*"([a-z0-9_]+)"\s+if\s+.*\s+else\s+"([a-z0-9_]+)"')
# Module-level stop-reason constants in tools/, e.g. STALE_RUN_STOP = "stale_run".
_CONSTANT = re.compile(r'^[A-Z][A-Z0-9_]*_STOP\s*=\s*"([a-z0-9_]+)"', re.MULTILINE)


def discover_stop_reasons() -> set[str]:
    """Every stop reason the runner source can put into ``state.stop_reason``."""
    found: set[str] = set()

    with open(os.path.join(_RUNNER_DIR, "graph.py")) as f:
        graph_src = f.read()
    found.update(_ASSIGNED.findall(graph_src))
    for a, b in _TERNARY.findall(graph_src):
        found.update({a, b})

    for name in sorted(os.listdir(_TOOLS_DIR)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(_TOOLS_DIR, name)) as f:
            source = f.read()
        found.update(_CONSTANT.findall(source))
        found.update(_ASSIGNED.findall(source))

    return found


class TestRegistryCoverage:
    def test_scanner_finds_the_known_stop_reasons(self):
        """Guards the guard: a scanner that silently matches nothing would make
        the coverage test below pass forever."""
        found = discover_stop_reasons()
        for reason in (
            "stale_run",
            "chatgpt_no_task",
            "consecutive_failures",
            "awaiting_resources",
            "seeded_queue_exhausted",
            "max_loop_tasks",
            "deploy_failed",
            "deploy_timed_out",
            "claude_subscription_cooldown",
        ):
            assert reason in found, f"scanner missed {reason}"
        assert len(found) >= 25

    def test_every_stop_reason_in_source_has_a_handler(self):
        missing = unhandled_stop_reasons(discover_stop_reasons())
        assert not missing, (
            "Stop reason(s) with no diagnostics handler: "
            + ", ".join(missing)
            + ". Add a StopHandler (cause + action + config_keys) to "
            "STOP_HANDLERS in tools/stop_diagnostics.py."
        )

    def test_every_handler_writes_a_cause_and_an_action(self):
        for reason, handler in STOP_HANDLERS.items():
            assert handler.reason == reason
            assert len(handler.headline) > 10, reason
            assert len(handler.cause) > 60, f"{reason}: cause is not a real sentence"
            assert len(handler.action) > 40, f"{reason}: action is not actionable"

    def test_every_action_names_a_command_or_a_config_change(self):
        """A RECOMMENDED ACTION that names nothing to run or change is just a
        restatement of the problem."""
        for reason, handler in STOP_HANDLERS.items():
            action = handler.action
            names_command = "`" in action
            names_config = re.search(r"\b[A-Z][A-Z0-9_]{4,}\b", action) is not None
            assert names_command or names_config, (
                f"{reason}: action names neither a command nor a config variable"
            )

    def test_handler_config_keys_exist_in_the_config_report(self):
        from config import RunnerConfig

        report = RunnerConfig().report()
        for reason, handler in STOP_HANDLERS.items():
            for key in handler.config_keys:
                assert key in report, f"{reason}: unknown config key {key!r}"

    def test_env_names_resolve_to_real_env_vars(self):
        with open(os.path.join(_RUNNER_DIR, "config.py")) as f:
            config_src = f.read()
        for handler in STOP_HANDLERS.values():
            for key in handler.config_keys:
                env = env_name_for(key)
                assert f'"{env}"' in config_src, (
                    f"{key} -> {env} is not read by config.py; fix "
                    "_ENV_NAME_OVERRIDES so the report names the real variable"
                )

    def test_no_handler_prints_a_credential(self):
        for reason, handler in STOP_HANDLERS.items():
            for key in handler.config_keys:
                assert not is_secret_key(key), f"{reason}: {key} looks like a secret"

    def test_expected_stops_all_have_handlers(self):
        assert not unhandled_stop_reasons(EXPECTED_STOP_REASONS)


# ---------------------------------------------------------------------------
# Classification — the field m4c-06's watchdog reads
# ---------------------------------------------------------------------------

class TestClassification:
    @pytest.mark.parametrize("reason", sorted(EXPECTED_STOP_REASONS))
    def test_expected_stops(self, reason):
        assert classify_stop(reason) == EXPECTED

    @pytest.mark.parametrize("reason", [
        "stale_run", "consecutive_failures", "awaiting_resources",
        "deploy_failed", "worker_timeouts", "chatgpt_no_task",
    ])
    def test_anomalous_stops(self, reason):
        assert classify_stop(reason) == ANOMALOUS

    def test_the_three_named_in_the_brief_are_expected(self):
        assert classify_stop("seeded_queue_exhausted") == EXPECTED
        assert classify_stop("max_loop_tasks") == EXPECTED
        assert classify_stop("claude_subscription_cooldown") == EXPECTED

    def test_unknown_reason_is_anomalous(self):
        assert classify_stop("something_nobody_registered") == ANOMALOUS

    def test_missing_reason_is_anomalous(self):
        assert classify_stop(None) == ANOMALOUS

    def test_missing_reason_falls_back_to_the_unspecified_handler(self):
        assert get_handler(None).reason == UNSPECIFIED_STOP


# ---------------------------------------------------------------------------
# Evidence collection
# ---------------------------------------------------------------------------

def _event(event_type, payload=None, task_id=None, timestamp="2026-08-03T04:00:00"):
    return {
        "event_type": event_type,
        "timestamp": timestamp,
        "task_id": task_id,
        "payload": payload or {},
    }


class TestCollectEvidence:
    def test_pulls_the_observed_numbers_from_the_matching_event(self):
        events = [
            _event("task_loaded"),
            _event("loop_blocked_on_stale_run", {
                "stale_minutes": 4106.0, "max_stale_task_minutes": 120,
            }),
        ]
        evidence = collect_evidence(events, get_handler("stale_run"))
        assert evidence["stale_minutes"] == 4106.0
        assert evidence["max_stale_task_minutes"] == 120

    def test_most_recent_match_wins(self):
        events = [
            _event("loop_blocked_on_stale_run", {"stale_minutes": 200}),
            _event("loop_blocked_on_stale_run", {"stale_minutes": 4106}),
        ]
        evidence = collect_evidence(events, get_handler("stale_run"))
        assert evidence["stale_minutes"] == 4106

    def test_generic_gate_event_is_matched_on_the_gate_that_fired(self):
        """Four gates share the gate_blocked event; reporting the definition-of-
        done issues under an acceptance-criteria stop would be a fresh
        misdiagnosis of exactly the kind this module exists to end."""
        events = [
            _event("gate_blocked", {"gate": "acceptance_criteria", "issues": ["no criteria"]}),
            _event("gate_blocked", {"gate": "definition_of_done", "issues": ["no summary"]}),
        ]
        evidence = collect_evidence(events, get_handler("missing_acceptance_criteria"))
        assert evidence["issues"] == ["no criteria"]

    def test_no_matching_event_returns_empty(self):
        assert collect_evidence([_event("task_loaded")], get_handler("stale_run")) == {}

    def test_no_handler_returns_empty(self):
        assert collect_evidence([_event("anything")], None) == {}

    def test_task_id_is_carried_over_from_the_event_envelope(self):
        events = [_event("loop_blocked_on_stale_run", {"stale_minutes": 9}, task_id="t-1")]
        assert collect_evidence(events, get_handler("stale_run"))["task_id"] == "t-1"


class TestCollectRecentEvents:
    def test_returns_the_last_five_oldest_first(self):
        events = [_event(f"e{i}") for i in range(10)]
        recent = collect_recent_events(events)
        assert [e["event_type"] for e in recent] == ["e5", "e6", "e7", "e8", "e9"]

    def test_shutdown_reporting_events_do_not_consume_the_five_slots(self):
        events = [_event(f"e{i}") for i in range(5)] + [
            _event("live_batch_validation_complete"),
            _event(STOP_REPORT_EVENT),
        ]
        recent = collect_recent_events(events)
        assert [e["event_type"] for e in recent] == ["e0", "e1", "e2", "e3", "e4"]

    def test_fewer_than_five_events_is_fine(self):
        assert len(collect_recent_events([_event("only")])) == 1

    def test_no_events_is_fine(self):
        assert collect_recent_events([]) == []


class TestCollectConfigValues:
    def test_reads_only_the_keys_the_handler_declared(self):
        values = collect_config_values(
            {"max_stale_task_minutes": 120, "unrelated": 7},
            get_handler("stale_run"),
        )
        assert values["max_stale_task_minutes"] == 120
        assert "unrelated" not in values

    def test_missing_key_reports_none_rather_than_raising(self):
        values = collect_config_values({}, get_handler("stale_run"))
        assert values["max_stale_task_minutes"] is None

    def test_secret_looking_keys_are_redacted(self):
        handler = sd.StopHandler(
            reason="x", headline="h", cause="c", action="a",
            config_keys=("anthropic_api_key",),
        )
        values = collect_config_values({"anthropic_api_key": "sk-real-value"}, handler)
        assert values["anthropic_api_key"] == "[redacted]"
        assert "sk-real-value" not in json.dumps(values)


# ---------------------------------------------------------------------------
# The report itself
# ---------------------------------------------------------------------------

def _state(**overrides):
    base = {
        "loop_count": 7,
        "started_at": "2026-08-03T00:00:00",
        "session_cost": 1.25,
        "consecutive_failures": 0,
        "worker_timeout_count": 0,
        "last_completed_step": "update_logs_and_state",
        "last_task_completed_at": "2026-07-31T08:00:00",
        "current_task_id": "m4c0-05",
        "current_worker": "claude",
        "current_task": {
            "id": "m4c0-05",
            "title": "Seeded queue task",
            "status": "blocked",
            "type": "backend",
            "branch": "feature/m4c0-05",
        },
    }
    base.update(overrides)
    return base


_CONFIG = {
    "max_stale_task_minutes": 120,
    "stale_run_warn_minutes": 75,
    "max_runtime_minutes": 480,
    "stale_run_watchdog_enabled": True,
    "max_loop_tasks": 10,
    "seeded_mission_queue_enabled": True,
    "seeded_mission_queue_strict": True,
}


class TestBuildStopDiagnostics:
    def _stale_run(self, **kwargs):
        events = [
            _event("task_completed", {"task_id": "m4c0-04"}),
            _event("loop_blocked_on_stale_run", {
                "stale_minutes": 4106.0,
                "max_stale_task_minutes": 120,
                "last_task_completed_at": "2026-07-31T08:00:00",
            }, task_id="m4c0-05"),
        ]
        return build_stop_diagnostics(
            stop_reason="stale_run",
            session_state=_state(),
            config_report=_CONFIG,
            events=events,
            **kwargs,
        )

    def test_prints_observed_and_configured_side_by_side(self):
        """The stale_run misdiagnosis happened because the report showed the
        threshold without the observed gap. Both must appear."""
        diag = self._stale_run()
        assert "4106.0" in diag["report"]
        assert "MAX_STALE_TASK_MINUTES" in diag["report"]
        assert "120" in diag["report"]

    def test_cause_and_action_are_rendered_with_real_numbers(self):
        diag = self._stale_run()
        assert "4106.0" in diag["cause"]
        assert "{" not in diag["cause"] and "{" not in diag["action"]
        assert "reset-state" in diag["action"]

    def test_one_threshold_name_never_shows_two_values(self):
        """Guards fire with the threshold in their payload too. If the event's
        copy won, the CAUSE sentence and the config section could print the same
        variable with different numbers — a misdiagnosis manufactured by the
        report meant to prevent one."""
        events = [_event("loop_blocked_on_stale_run", {
            "stale_minutes": 4106.0, "max_stale_task_minutes": 120,
        })]
        diag = build_stop_diagnostics(
            stop_reason="stale_run",
            session_state=_state(),
            config_report={**_CONFIG, "max_stale_task_minutes": 180},
            events=events,
        )
        assert "MAX_STALE_TASK_MINUTES (180)" in diag["cause"]
        assert "120" not in diag["cause"]
        assert "max_stale_task_minutes" not in diag["evidence"]
        assert diag["evidence"]["stale_minutes"] == 4106.0

    def test_gate_bookkeeping_is_not_reported_as_an_observation(self):
        events = [_event("loop_blocked_on_stale_run", {
            "gate": "stale_run", "authority": "runner", "stale_minutes": 300,
        })]
        diag = build_stop_diagnostics(
            stop_reason="stale_run", session_state=_state(),
            config_report=_CONFIG, events=events,
        )
        assert set(diag["evidence"]) == {"stale_minutes"}

    def test_report_carries_every_required_section(self):
        report = self._stale_run()["report"]
        for section in (
            "LOOP STOP REPORT",
            "TRIGGERING TASK",
            "CAUSE",
            "RECOMMENDED ACTION",
            "CONFIG THAT PRODUCED THIS STOP",
            "PRECEDING",
        ):
            assert section in report, section

    def test_report_names_the_triggering_task_and_its_status(self):
        report = self._stale_run()["report"]
        assert "m4c0-05" in report
        assert "blocked" in report

    def test_report_quotes_the_preceding_events(self):
        diag = self._stale_run()
        assert len(diag["recent_events"]) == 2
        assert "loop_blocked_on_stale_run" in diag["report"]
        assert "task_completed" in diag["report"]

    def test_classification_is_marked_in_the_report(self):
        assert "ANOMALOUS" in self._stale_run()["report"]

    def test_expected_stop_is_marked_expected(self):
        diag = build_stop_diagnostics(
            stop_reason="seeded_queue_exhausted",
            session_state=_state(),
            config_report=_CONFIG,
            events=[],
        )
        assert diag["classification"] == EXPECTED
        assert "EXPECTED" in diag["report"]
        assert "ANOMALOUS" not in diag["report"]

    def test_chatgpt_no_task_points_at_the_queue_before_the_planner(self):
        """The other historical misdiagnosis: a strict-mode-exhausted queue read
        as a planner fault."""
        diag = build_stop_diagnostics(
            stop_reason="chatgpt_no_task",
            session_state=_state(),
            config_report=_CONFIG,
            events=[],
        )
        assert "SEEDED_MISSION_QUEUE_STRICT" in diag["report"]
        assert "doctor" in diag["action"]

    def test_unknown_stop_reason_is_reported_loudly_not_silently(self):
        diag = build_stop_diagnostics(
            stop_reason="brand_new_reason",
            session_state=_state(),
            config_report=_CONFIG,
            events=[],
        )
        assert diag["handler_found"] is False
        assert diag["classification"] == ANOMALOUS
        assert "brand_new_reason" in diag["cause"]
        assert "stop_diagnostics.py" in diag["action"]

    def test_missing_stop_reason_reports_the_missing_reason_itself(self):
        diag = build_stop_diagnostics(
            stop_reason=None,
            session_state=_state(),
            config_report=_CONFIG,
            events=[],
        )
        assert diag["reason"] == UNSPECIFIED_STOP
        assert diag["handler_found"] is True
        assert "update_logs_and_state" in diag["action"]

    def test_task_falls_back_to_state_when_not_passed(self):
        diag = build_stop_diagnostics(
            stop_reason="stale_run",
            session_state=_state(),
            config_report=_CONFIG,
            events=[],
        )
        assert diag["task"]["id"] == "m4c0-05"

    def test_explicit_task_argument_wins(self):
        diag = build_stop_diagnostics(
            stop_reason="stale_run",
            session_state=_state(),
            config_report=_CONFIG,
            events=[],
            task={"id": "other", "title": "T", "status": "queued"},
        )
        assert diag["task"]["id"] == "other"

    def test_empty_everything_still_produces_a_report(self):
        diag = build_stop_diagnostics(
            stop_reason="max_loop_tasks",
            session_state={},
            config_report={},
            events=[],
        )
        assert "LOOP STOP REPORT" in diag["report"]
        assert diag["classification"] == EXPECTED


class TestConsistencyWarnings:
    """A stop_reason inherited from a previous session reproduces a real stop
    exactly — observed on a dry-run that reported max_loop_tasks at loop_count 0
    with MAX_LOOP_TASKS=2. Narrating that in the same confident voice as a true
    budget stop is the misdiagnosis this module exists to end."""

    def test_max_loop_tasks_below_its_own_budget_is_flagged(self):
        diag = build_stop_diagnostics(
            stop_reason="max_loop_tasks",
            session_state=_state(loop_count=0),
            config_report={"max_loop_tasks": 2, "max_runtime_minutes": 480},
            events=[],
        )
        assert diag["warnings"]
        assert "reset-state" in diag["warnings"][0]
        assert "SUSPECT — READ THIS FIRST" in diag["report"]
        assert ":warning: *SUSPECT*" in diag["slack_message"]

    def test_a_genuine_budget_stop_is_not_flagged(self):
        diag = build_stop_diagnostics(
            stop_reason="max_loop_tasks",
            session_state=_state(loop_count=10),
            config_report={"max_loop_tasks": 10, "max_runtime_minutes": 480},
            events=[],
        )
        assert diag["warnings"] == []
        assert "SUSPECT" not in diag["report"]

    def test_max_runtime_well_inside_its_window_is_flagged(self):
        from datetime import datetime, timedelta

        started = (datetime.utcnow() - timedelta(minutes=3)).isoformat()
        diag = build_stop_diagnostics(
            stop_reason="max_runtime",
            session_state=_state(started_at=started),
            config_report={**_CONFIG, "max_runtime_minutes": 480},
            events=[],
        )
        assert diag["warnings"]

    def test_a_genuine_runtime_stop_is_not_flagged(self):
        from datetime import datetime, timedelta

        started = (datetime.utcnow() - timedelta(minutes=500)).isoformat()
        diag = build_stop_diagnostics(
            stop_reason="max_runtime",
            session_state=_state(started_at=started),
            config_report={**_CONFIG, "max_runtime_minutes": 480},
            events=[],
        )
        assert diag["warnings"] == []

    def test_unparseable_or_missing_numbers_never_raise(self):
        for state_kwargs, config in (
            ({"loop_count": None}, {"max_loop_tasks": 2}),
            ({"started_at": "not-a-timestamp"}, {"max_runtime_minutes": 10}),
            ({}, {}),
        ):
            diag = build_stop_diagnostics(
                stop_reason="max_loop_tasks",
                session_state=_state(**state_kwargs),
                config_report=config,
                events=[],
            )
            assert isinstance(diag["warnings"], list)

    def test_other_stop_reasons_are_left_alone(self):
        diag = build_stop_diagnostics(
            stop_reason="stale_run", session_state=_state(loop_count=0),
            config_report=_CONFIG, events=[],
        )
        assert diag["warnings"] == []


class TestSlackMessage:
    def test_classification_leads_the_message(self):
        diag = build_stop_diagnostics(
            stop_reason="stale_run", session_state=_state(),
            config_report=_CONFIG, events=[],
        )
        assert diag["slack_message"].splitlines()[0].startswith(":rotating_light: *ANOMALOUS*")

    def test_expected_stop_uses_the_finished_marker(self):
        diag = build_stop_diagnostics(
            stop_reason="max_loop_tasks", session_state=_state(),
            config_report=_CONFIG, events=[],
        )
        assert ":checkered_flag: *EXPECTED*" in diag["slack_message"]

    def test_message_carries_cause_action_task_and_config(self):
        diag = build_stop_diagnostics(
            stop_reason="stale_run", session_state=_state(),
            config_report=_CONFIG, events=[],
        )
        message = diag["slack_message"]
        assert "*CAUSE*" in message
        assert "*RECOMMENDED ACTION*" in message
        assert "m4c0-05" in message
        assert "MAX_STALE_TASK_MINUTES=120" in message
        assert STOP_REPORT_FILENAME in message

    def test_message_lists_the_event_trail(self):
        diag = build_stop_diagnostics(
            stop_reason="stale_run", session_state=_state(),
            config_report=_CONFIG,
            events=[_event("task_completed"), _event("loop_blocked_on_stale_run", {})],
        )
        assert "task_completed → loop_blocked_on_stale_run" in diag["slack_message"]

    def test_slack_renderer_passes_the_message_through_verbatim(self):
        from tools.slack_tools import format_event

        text = format_event("loop_stop_report", {"message": "*ANOMALOUS* — cause\naction"})
        assert "*ANOMALOUS* — cause" in text
        assert "action" in text

    def test_stop_report_is_a_notable_slack_event_by_default(self):
        from config import _DEFAULT_SLACK_EVENTS

        assert STOP_REPORT_EVENT in _DEFAULT_SLACK_EVENTS


# ---------------------------------------------------------------------------
# report_loop_stop — one file, one message
# ---------------------------------------------------------------------------

class TestReportLoopStop:
    @pytest.fixture(autouse=True)
    def _capture_events(self, monkeypatch):
        self.logged = []
        monkeypatch.setattr(
            sd, "log_event",
            lambda event_type, payload, task_id=None: self.logged.append(
                (event_type, payload, task_id)
            ),
        )

    def test_writes_one_record_and_fires_one_message(self, tmp_path):
        diag = report_loop_stop(
            stop_reason="stale_run",
            session_state=_state(),
            config_report=_CONFIG,
            outbox_dir=tmp_path,
            events=[_event("loop_blocked_on_stale_run", {"stale_minutes": 4106.0})],
        )

        written = (tmp_path / STOP_REPORT_FILENAME).read_text()
        assert "LOOP STOP REPORT — ANOMALOUS" in written
        assert diag["report_path"] == str(tmp_path / STOP_REPORT_FILENAME)

        assert len(self.logged) == 1
        event_type, payload, task_id = self.logged[0]
        assert event_type == STOP_REPORT_EVENT
        assert payload["classification"] == ANOMALOUS
        assert payload["recommended_action"]
        assert payload["message"] == diag["slack_message"]
        assert task_id == "m4c0-05"

    def test_event_payload_is_structured_for_the_watchdog(self, tmp_path):
        report_loop_stop(
            stop_reason="max_loop_tasks",
            session_state=_state(),
            config_report=_CONFIG,
            outbox_dir=tmp_path,
            events=[],
        )
        payload = self.logged[0][1]
        assert payload["reason"] == "max_loop_tasks"
        assert payload["classification"] == EXPECTED
        assert payload["handler_found"] is True
        assert isinstance(payload["preceding_events"], list)

    def test_creates_the_outbox_directory(self, tmp_path):
        outbox = tmp_path / "nested" / "outbox"
        report_loop_stop(
            stop_reason="max_loop_tasks", session_state=_state(),
            config_report=_CONFIG, outbox_dir=outbox, events=[],
        )
        assert (outbox / STOP_REPORT_FILENAME).exists()

    def test_rewrites_rather_than_appends_across_runs(self, tmp_path):
        for reason in ("stale_run", "max_loop_tasks"):
            report_loop_stop(
                stop_reason=reason, session_state=_state(),
                config_report=_CONFIG, outbox_dir=tmp_path, events=[],
            )
        written = (tmp_path / STOP_REPORT_FILENAME).read_text()
        assert written.count("LOOP STOP REPORT") == 1
        assert "max_loop_tasks" in written

    def test_a_write_failure_never_breaks_the_stop_path(self, tmp_path, monkeypatch):
        blocked = tmp_path / "outbox"
        blocked.write_text("not a directory")
        diag = report_loop_stop(
            stop_reason="stale_run", session_state=_state(),
            config_report=_CONFIG, outbox_dir=blocked, events=[],
        )
        assert diag["report_path"] is None
        assert diag["write_error"]
        # The diagnosis still reaches Slack even when the file cannot be written.
        assert self.logged[0][0] == STOP_REPORT_EVENT


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

class TestGraphWiring:
    def test_the_stop_report_node_is_on_the_terminal_edge(self):
        with open(os.path.join(_RUNNER_DIR, "graph.py")) as f:
            src = f.read()
        assert 'add_node("report_loop_stop_diagnostics"' in src
        assert 'add_edge("generate_live_batch_validation_report", "report_loop_stop_diagnostics")' in src
        assert 'add_edge("report_loop_stop_diagnostics", END)' in src

    def test_node_reports_and_never_raises(self, monkeypatch, tmp_path):
        import graph as graph_module
        from state import RunnerState

        monkeypatch.setattr(graph_module, "_RUNNER_DIR", tmp_path)
        calls = []
        monkeypatch.setattr(
            graph_module, "report_loop_stop",
            lambda **kwargs: calls.append(kwargs) or {},
        )

        state = RunnerState(stop_reason="stale_run", loop_count=3, current_task_id="t-1")
        out = graph_module.report_loop_stop_diagnostics(state)

        assert out.stop_reason == "stale_run"
        assert calls[0]["stop_reason"] == "stale_run"
        assert calls[0]["outbox_dir"] == tmp_path / "outbox"

    def test_a_failing_reporter_does_not_break_the_run(self, monkeypatch, tmp_path):
        import graph as graph_module
        from state import RunnerState

        monkeypatch.setattr(graph_module, "_RUNNER_DIR", tmp_path)

        def _boom(**kwargs):
            raise RuntimeError("diagnostics exploded")

        monkeypatch.setattr(graph_module, "report_loop_stop", _boom)
        events = []
        monkeypatch.setattr(
            graph_module, "log_event",
            lambda event_type, payload, task_id=None: events.append(event_type),
        )

        out = graph_module.report_loop_stop_diagnostics(
            RunnerState(stop_reason="max_loop_tasks")
        )
        assert out.stop_reason == "max_loop_tasks"
        assert "stop_diagnostics_degraded" in events


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
