"""Unit tests for tools/posthog_tools.py — mocked HTTP only, no live PostHog calls."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from config import get_config
import tools.posthog_tools as pt

# Keep the flight recorder quiet during tests.
pt.log_event = lambda *a, **k: None


def _cfg(**overrides):
    """Fresh config with PostHog credentials set (and any overrides applied)."""
    config._config = None
    cfg = get_config()
    cfg.posthog_personal_api_key = overrides.get("posthog_personal_api_key", "phx_test_key")
    cfg.posthog_project_id = overrides.get("posthog_project_id", "12345")
    cfg.posthog_host = overrides.get("posthog_host", "https://us.i.posthog.com")
    return cfg


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.exceptions.HTTPError(response=self)

    def json(self):
        return self._json


# ---------------------------------------------------------------------------
# query_event_count
# ---------------------------------------------------------------------------

def test_query_event_count_no_credentials():
    config._config = None
    cfg = get_config()
    cfg.posthog_personal_api_key = None
    cfg.posthog_project_id = None
    res = pt.query_event_count("signup_completed", days=7)
    assert res["available"] is False, res
    assert "POSTHOG" in res["reason"], res


def test_query_event_count_success(monkeypatch):
    _cfg()
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse({"results": [[42]]})

    monkeypatch.setattr(pt.requests, "post", fake_post)
    res = pt.query_event_count("signup_completed", days=14)

    assert res["available"] is True, res
    assert res["count"] == 42, res
    assert res["event"] == "signup_completed", res
    assert res["days"] == 14, res
    assert captured["url"] == "https://us.i.posthog.com/api/projects/12345/query/"
    assert captured["headers"]["Authorization"] == "Bearer phx_test_key"
    assert "signup_completed" in captured["json"]["query"]["query"]


def test_query_event_count_escapes_quotes(monkeypatch):
    _cfg()
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _FakeResponse({"results": [[1]]})

    monkeypatch.setattr(pt.requests, "post", fake_post)
    pt.query_event_count("weird'event", days=1)
    assert "weird\\'event" in captured["json"]["query"]["query"]


def test_query_event_count_empty_results_defaults_to_zero(monkeypatch):
    _cfg()
    monkeypatch.setattr(pt.requests, "post", lambda *a, **k: _FakeResponse({"results": []}))
    res = pt.query_event_count("signup_completed")
    assert res["available"] is True, res
    assert res["count"] == 0, res


def test_query_event_count_http_error(monkeypatch):
    _cfg()

    def fake_post(*a, **k):
        return _FakeResponse({}, status_code=500)

    monkeypatch.setattr(pt.requests, "post", fake_post)
    res = pt.query_event_count("signup_completed")
    assert res["available"] is False, res
    assert "error" in res, res


def test_query_event_count_unexpected_shape(monkeypatch):
    _cfg()
    monkeypatch.setattr(pt.requests, "post", lambda *a, **k: _FakeResponse({"results": [["not-an-int"]]}))
    res = pt.query_event_count("signup_completed")
    assert res["available"] is False, res
    assert "unexpected response shape" in res["error"], res


# ---------------------------------------------------------------------------
# query_funnel
# ---------------------------------------------------------------------------

def test_query_funnel_no_credentials():
    config._config = None
    cfg = get_config()
    cfg.posthog_personal_api_key = None
    cfg.posthog_project_id = None
    res = pt.query_funnel(["signup_started", "signup_completed"])
    assert res["available"] is False, res


def test_query_funnel_no_events():
    _cfg()
    res = pt.query_funnel([])
    assert res["available"] is False, res
    assert "no events" in res["error"], res


def test_query_funnel_success(monkeypatch):
    _cfg()
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _FakeResponse({
            "results": [
                {"name": "signup_started", "count": 100},
                {"name": "signup_completed", "count": 40},
            ]
        })

    monkeypatch.setattr(pt.requests, "post", fake_post)
    res = pt.query_funnel(["signup_started", "signup_completed"], days=30)

    assert res["available"] is True, res
    assert res["steps"] == [
        {"name": "signup_started", "count": 100},
        {"name": "signup_completed", "count": 40},
    ], res
    assert captured["json"]["query"]["kind"] == "FunnelsQuery"
    assert captured["json"]["query"]["dateRange"] == {"date_from": "-30d"}


def test_query_funnel_unwraps_nested_results(monkeypatch):
    _cfg()

    def fake_post(*a, **k):
        return _FakeResponse({
            "results": [[
                {"name": "signup_started", "count": 10},
                {"name": "signup_completed", "count": 5},
            ]]
        })

    monkeypatch.setattr(pt.requests, "post", fake_post)
    res = pt.query_funnel(["signup_started", "signup_completed"])
    assert res["available"] is True, res
    assert res["steps"][0]["count"] == 10, res


def test_query_funnel_http_error(monkeypatch):
    _cfg()
    monkeypatch.setattr(pt.requests, "post", lambda *a, **k: _FakeResponse({}, status_code=502))
    res = pt.query_funnel(["a", "b"])
    assert res["available"] is False, res
    assert "error" in res, res


# ---------------------------------------------------------------------------
# format_analytics_summary (pure)
# ---------------------------------------------------------------------------

def test_format_summary_empty():
    assert pt.format_analytics_summary() == "No analytics data requested."


def test_format_summary_event_counts():
    summary = pt.format_analytics_summary(
        event_counts={"Signups": {"available": True, "count": 42, "days": 7}}
    )
    assert summary == "Signups: 42 events over 7d", summary


def test_format_summary_event_counts_unavailable():
    summary = pt.format_analytics_summary(
        event_counts={"Signups": {"available": False, "reason": "no POSTHOG_PERSONAL_API_KEY/POSTHOG_PROJECT_ID"}}
    )
    assert summary == "Signups: unavailable (no POSTHOG_PERSONAL_API_KEY/POSTHOG_PROJECT_ID)", summary


def test_format_summary_funnel():
    summary = pt.format_analytics_summary(
        funnels={
            "Signup funnel": {
                "available": True,
                "steps": [
                    {"name": "started", "count": 100},
                    {"name": "completed", "count": 25},
                ],
            }
        }
    )
    assert summary == "Signup funnel: started=100 (100%) -> completed=25 (25%)", summary


def test_format_summary_funnel_unavailable():
    summary = pt.format_analytics_summary(
        funnels={"Signup funnel": {"available": False, "error": "boom"}}
    )
    assert summary == "Signup funnel: unavailable (boom)", summary


def test_format_summary_funnel_no_steps():
    summary = pt.format_analytics_summary(
        funnels={"Signup funnel": {"available": True, "steps": []}}
    )
    assert summary == "Signup funnel: no steps returned", summary


def test_format_summary_combines_sections():
    summary = pt.format_analytics_summary(
        event_counts={"Signups": {"available": True, "count": 5, "days": 1}},
        funnels={"F": {"available": True, "steps": [{"name": "a", "count": 2}]}},
    )
    assert summary == "Signups: 5 events over 1d\nF: a=2 (100%)", summary


if __name__ == "__main__":
    import pytest as _pytest

    sys.exit(_pytest.main([__file__, "-q"]))
