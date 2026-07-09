"""Unit tests for tools/analytics_report.py.

Covers the pure formatting/aggregation helpers with fixture data (no network),
plus generate_analytics_report's outbox write / log_event wiring against a
temp directory with query_funnel and list_new_issues monkeypatched.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from config import get_config
import tools.analytics_report as ar

ar.log_event = lambda *a, **k: None


def _cfg_with_sentry(**overrides):
    config._config = None
    cfg = get_config()
    cfg.sentry_auth_token = overrides.get("sentry_auth_token", "test-token")
    cfg.sentry_org = overrides.get("sentry_org", "acme")
    cfg.sentry_project = overrides.get("sentry_project", "web")
    return cfg


def _cfg_without_sentry():
    config._config = None
    cfg = get_config()
    cfg.sentry_auth_token = None
    cfg.sentry_org = None
    cfg.sentry_project = None
    return cfg


# ---------------------------------------------------------------------------
# format_funnel_lines
# ---------------------------------------------------------------------------

def test_format_funnel_lines_available():
    result = {
        "available": True,
        "steps": [
            {"name": "user_signed_up", "count": 100},
            {"name": "repo_created", "count": 30},
            {"name": "deploy_succeeded", "count": 12},
        ],
    }
    lines = ar.format_funnel_lines(result)
    assert lines == [
        "  user_signed_up: 100 (100%)",
        "  repo_created: 30 (30%)",
        "  deploy_succeeded: 12 (12%)",
    ], lines


def test_format_funnel_lines_not_configured():
    result = {"available": False, "reason": "no POSTHOG_PERSONAL_API_KEY/POSTHOG_PROJECT_ID"}
    lines = ar.format_funnel_lines(result)
    assert lines == ["  not configured (no POSTHOG_PERSONAL_API_KEY/POSTHOG_PROJECT_ID)"], lines


def test_format_funnel_lines_error():
    result = {"available": False, "error": "connection refused"}
    lines = ar.format_funnel_lines(result)
    assert lines == ["  not configured (connection refused)"], lines


def test_format_funnel_lines_no_steps():
    result = {"available": True, "steps": []}
    lines = ar.format_funnel_lines(result)
    assert lines == ["  no funnel data returned"], lines


# ---------------------------------------------------------------------------
# format_sentry_lines
# ---------------------------------------------------------------------------

def test_format_sentry_lines_not_configured():
    lines = ar.format_sentry_lines(False, [])
    assert lines == ["  not configured (missing SENTRY_AUTH_TOKEN/SENTRY_ORG/SENTRY_PROJECT)"], lines


def test_format_sentry_lines_no_new_issues():
    lines = ar.format_sentry_lines(True, [])
    assert lines == ["  no new issues"], lines


def test_format_sentry_lines_with_issues():
    issues = [
        {"short_id": "PROJ-1", "title": "TypeError: boom", "count": 5, "user_count": 2},
        {"short_id": "PROJ-2", "title": "ReferenceError: bar", "count": 1, "user_count": 1},
    ]
    lines = ar.format_sentry_lines(True, issues)
    assert lines == [
        "  [PROJ-1] TypeError: boom (count=5, users=2)",
        "  [PROJ-2] ReferenceError: bar (count=1, users=1)",
    ], lines


def test_format_sentry_lines_truncates_beyond_max():
    issues = [
        {"short_id": f"PROJ-{i}", "title": "err", "count": 1, "user_count": 1}
        for i in range(15)
    ]
    lines = ar.format_sentry_lines(True, issues)
    assert len(lines) == ar._MAX_SENTRY_ISSUE_LINES + 1, lines
    assert lines[-1] == "  ... and 5 more", lines


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

_FUNNEL_AVAILABLE = {
    "available": True,
    "events": ar.CANONICAL_FUNNEL_EVENTS,
    "days": 7,
    "steps": [
        {"name": "user_signed_up", "count": 200},
        {"name": "intake_started", "count": 150},
        {"name": "intake_submitted", "count": 120},
        {"name": "blueprint_generated", "count": 100},
        {"name": "blueprint_saved", "count": 80},
        {"name": "tool_approval_requested", "count": 70},
        {"name": "tool_approved", "count": 60},
        {"name": "repo_created", "count": 45},
        {"name": "scaffold_prepared", "count": 40},
        {"name": "vercel_project_created", "count": 35},
        {"name": "deploy_succeeded", "count": 22},
    ],
}


def test_build_report_headline_reports_deploy_succeeded_count():
    result = ar.build_report(
        funnel_result=_FUNNEL_AVAILABLE,
        sentry_available=True,
        sentry_issues=[],
        days=7,
        generated_at="2026-07-09T00:00:00+00:00",
    )
    assert result["headline"] == "Users who reached a deployed repo this week: 22", result["headline"]
    assert result["deploy_succeeded_count"] == 22, result
    assert result["repo_created_count"] == 45, result
    assert "Users who reached a deployed repo this week: 22" in result["text"], result["text"]
    assert "Unique users reaching repo_created     : 45" in result["text"], result["text"]
    assert "Unique users reaching deploy_succeeded : 22" in result["text"], result["text"]


def test_build_report_degraded_funnel_headline_not_configured():
    result = ar.build_report(
        funnel_result={"available": False, "reason": "no POSTHOG_PERSONAL_API_KEY/POSTHOG_PROJECT_ID"},
        sentry_available=True,
        sentry_issues=[],
        days=7,
    )
    assert result["headline"] == (
        "Users who reached a deployed repo this week: "
        "not configured (no POSTHOG_PERSONAL_API_KEY/POSTHOG_PROJECT_ID)"
    ), result["headline"]
    assert result["deploy_succeeded_count"] is None, result
    assert result["repo_created_count"] is None, result
    assert "not configured" in result["text"], result["text"]


def test_build_report_degraded_sentry_renders_not_configured_without_failing():
    result = ar.build_report(
        funnel_result=_FUNNEL_AVAILABLE,
        sentry_available=False,
        sentry_issues=[],
        days=7,
    )
    assert result["sentry_new_issue_count"] is None, result
    assert "not configured (missing SENTRY_AUTH_TOKEN/SENTRY_ORG/SENTRY_PROJECT)" in result["text"], result["text"]
    # Funnel section still renders fully even though Sentry is degraded.
    assert "deploy_succeeded: 22 (11%)" in result["text"], result["text"]


def test_build_report_both_degraded_still_produces_full_text():
    result = ar.build_report(
        funnel_result={"available": False, "error": "boom"},
        sentry_available=False,
        sentry_issues=[],
        days=7,
    )
    assert "not configured (boom)" in result["text"], result["text"]
    assert "not configured (missing SENTRY_AUTH_TOKEN/SENTRY_ORG/SENTRY_PROJECT)" in result["text"], result["text"]
    assert result["text"].strip() != "", result["text"]


# ---------------------------------------------------------------------------
# generate_analytics_report — outbox write + log_event wiring
# ---------------------------------------------------------------------------

def _with_temp_runner_dir(fn):
    original = ar._RUNNER_DIR
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        ar._RUNNER_DIR = root
        try:
            return fn(root)
        finally:
            ar._RUNNER_DIR = original


def test_generate_analytics_report_writes_outbox_file(monkeypatch):
    _cfg_with_sentry()
    monkeypatch.setattr(ar, "query_funnel", lambda events, days=7: _FUNNEL_AVAILABLE)
    monkeypatch.setattr(ar, "list_new_issues", lambda since_iso: [])

    events = []
    monkeypatch.setattr(ar, "log_event", lambda event_type, payload: events.append((event_type, payload)))

    def body(root):
        result = ar.generate_analytics_report(days=7)
        report_path = root / "outbox" / "analytics_report.txt"
        assert report_path.exists(), "report should be written to outbox/analytics_report.txt"
        assert report_path.read_text() == result["text"]
        return result

    result = _with_temp_runner_dir(body)
    assert result["deploy_succeeded_count"] == 22, result
    assert events and events[0][0] == "analytics_report_ready", events
    assert events[0][1]["deploy_succeeded_count"] == 22, events


def test_generate_analytics_report_degrades_without_crashing(monkeypatch):
    _cfg_without_sentry()
    monkeypatch.setattr(
        ar, "query_funnel",
        lambda events, days=7: {"available": False, "reason": "no POSTHOG_PERSONAL_API_KEY/POSTHOG_PROJECT_ID"},
    )
    monkeypatch.setattr(ar, "list_new_issues", lambda since_iso: [])
    monkeypatch.setattr(ar, "log_event", lambda *a, **k: None)

    def body(root):
        return ar.generate_analytics_report(days=7)

    result = _with_temp_runner_dir(body)
    assert "not configured" in result["headline"], result
    assert result["sentry_new_issue_count"] is None, result


if __name__ == "__main__":
    import pytest as _pytest

    sys.exit(_pytest.main([__file__, "-q"]))
