"""Unit tests for tools/sentry_tools.py.

Covers two layers:
  1. Pure parsing/aggregation/formatting helpers (parse_issue,
     filter_issues_since, summarize_issues, format_issue_summary) exercised
     against fixture payloads shaped like the real Sentry issues API — no
     network involved.
  2. list_new_issues / issue_summary — requests.get is stubbed (no network);
     both degrade to a safe no-op when Sentry credentials are absent.

Runs standalone (no pytest dependency), mirroring test_pr_merge_flow.py:

    python tests/test_sentry_tools.py
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests

import tools.sentry_tools as sentry_tools
from tools.sentry_tools import (
    filter_issues_since,
    format_issue_summary,
    issue_summary,
    list_new_issues,
    parse_issue,
    summarize_issues,
)

sentry_tools.log_event = lambda *a, **k: None


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

RAW_ISSUE_OLD = {
    "id": "1",
    "shortId": "PROJ-1",
    "title": "TypeError: Cannot read property 'foo' of undefined",
    "culprit": "app/utils.js in processData",
    "level": "error",
    "status": "unresolved",
    "count": "42",
    "userCount": 7,
    "firstSeen": "2026-01-01T10:00:00Z",
    "lastSeen": "2026-01-08T12:00:00Z",
    "permalink": "https://sentry.io/organizations/acme/issues/1/",
    "metadata": {"type": "TypeError"},
}

RAW_ISSUE_NEW = {
    "id": "2",
    "shortId": "PROJ-2",
    "title": "ReferenceError: bar is not defined",
    "culprit": "app/index.js in main",
    "level": "warning",
    "status": "unresolved",
    "count": "5",
    "userCount": 2,
    "firstSeen": "2026-07-05T09:00:00Z",
    "lastSeen": "2026-07-08T09:00:00Z",
    "permalink": "https://sentry.io/organizations/acme/issues/2/",
    "metadata": {"type": "ReferenceError"},
}

RAW_ISSUE_NO_TITLE = {
    "id": "3",
    "shortId": "PROJ-3",
    "level": "fatal",
    "status": "unresolved",
    "count": "1",
    "userCount": 0,
    "firstSeen": "2026-07-06T09:00:00Z",
    "lastSeen": "2026-07-06T09:00:00Z",
    "permalink": "https://sentry.io/organizations/acme/issues/3/",
    "metadata": {"type": "SegfaultError"},
}


class _FakeConfig:
    def __init__(self, auth_token="test-token", org="acme", project="web"):
        self.sentry_auth_token = auth_token
        self.sentry_org = org
        self.sentry_project = project

    @property
    def has_sentry(self):
        return bool(self.sentry_auth_token and self.sentry_org and self.sentry_project)


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = [] if json_data is None else json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._json_data


def _with_fake_config(cfg, fn):
    original = sentry_tools.get_config
    sentry_tools.get_config = lambda: cfg
    try:
        return fn()
    finally:
        sentry_tools.get_config = original


# ---------------------------------------------------------------------------
# parse_issue
# ---------------------------------------------------------------------------

def test_parse_issue_maps_known_fields():
    parsed = parse_issue(RAW_ISSUE_OLD)
    assert parsed["id"] == "1", parsed
    assert parsed["short_id"] == "PROJ-1", parsed
    assert parsed["title"] == "TypeError: Cannot read property 'foo' of undefined", parsed
    assert parsed["level"] == "error", parsed
    assert parsed["count"] == 42, parsed
    assert parsed["user_count"] == 7, parsed
    assert parsed["first_seen"] == "2026-01-01T10:00:00Z", parsed


def test_parse_issue_falls_back_to_metadata_type_for_title():
    parsed = parse_issue(RAW_ISSUE_NO_TITLE)
    assert parsed["title"] == "SegfaultError", parsed


def test_parse_issue_handles_missing_counts():
    parsed = parse_issue({"id": "9"})
    assert parsed["count"] == 0, parsed
    assert parsed["user_count"] == 0, parsed
    assert parsed["title"] == "unknown", parsed


# ---------------------------------------------------------------------------
# filter_issues_since
# ---------------------------------------------------------------------------

def test_filter_issues_since_keeps_only_recent():
    issues = [parse_issue(RAW_ISSUE_OLD), parse_issue(RAW_ISSUE_NEW)]
    kept = filter_issues_since(issues, "2026-07-01T00:00:00Z")
    assert [i["id"] for i in kept] == ["2"], kept


def test_filter_issues_since_no_cutoff_returns_all():
    issues = [parse_issue(RAW_ISSUE_OLD), parse_issue(RAW_ISSUE_NEW)]
    kept = filter_issues_since(issues, "")
    assert len(kept) == 2, kept


def test_filter_issues_since_unparseable_cutoff_returns_all():
    issues = [parse_issue(RAW_ISSUE_OLD), parse_issue(RAW_ISSUE_NEW)]
    kept = filter_issues_since(issues, "not-a-date")
    assert len(kept) == 2, kept


def test_filter_issues_since_missing_first_seen_is_kept():
    issues = [parse_issue({"id": "x"})]
    kept = filter_issues_since(issues, "2026-07-01T00:00:00Z")
    assert len(kept) == 1, kept


# ---------------------------------------------------------------------------
# summarize_issues / format_issue_summary
# ---------------------------------------------------------------------------

def test_summarize_issues_aggregates_counts():
    issues = [parse_issue(RAW_ISSUE_OLD), parse_issue(RAW_ISSUE_NEW)]
    summary = summarize_issues(issues)
    assert summary["total"] == 2, summary
    assert summary["by_level"] == {"error": 1, "warning": 1}, summary
    assert summary["total_events"] == 47, summary
    assert summary["total_users_affected"] == 9, summary
    assert summary["top_issues"][0]["id"] == "1", summary["top_issues"]


def test_summarize_issues_empty():
    summary = summarize_issues([])
    assert summary["total"] == 0, summary
    assert summary["by_level"] == {}, summary
    assert summary["top_issues"] == [], summary


def test_format_issue_summary_no_issues():
    text = format_issue_summary(summarize_issues([]))
    assert text == "Sentry: no unresolved issues.", text


def test_format_issue_summary_includes_counts_and_top_issues():
    issues = [parse_issue(RAW_ISSUE_OLD), parse_issue(RAW_ISSUE_NEW)]
    text = format_issue_summary(summarize_issues(issues))
    assert "2 unresolved issue(s)" in text, text
    assert "PROJ-1" in text, text
    assert "PROJ-2" in text, text


# ---------------------------------------------------------------------------
# list_new_issues — degraded / network
# ---------------------------------------------------------------------------

def test_list_new_issues_degrades_without_credentials():
    result = _with_fake_config(
        _FakeConfig(auth_token=None),
        lambda: list_new_issues("2026-07-01T00:00:00Z"),
    )
    assert result == [], result


def test_list_new_issues_missing_org_degrades():
    result = _with_fake_config(
        _FakeConfig(org=None),
        lambda: list_new_issues("2026-07-01T00:00:00Z"),
    )
    assert result == [], result


def test_list_new_issues_success():
    def _get(url, headers=None, params=None, timeout=None):
        assert "acme" in url and "web" in url, url
        assert headers["Authorization"] == "Bearer test-token", headers
        assert params["start"] == "2026-07-01T00:00:00Z", params
        return _FakeResponse(200, json_data=[RAW_ISSUE_OLD, RAW_ISSUE_NEW])

    sentry_tools.requests.get = _get
    result = _with_fake_config(
        _FakeConfig(),
        lambda: list_new_issues("2026-07-01T00:00:00Z"),
    )
    assert [i["id"] for i in result] == ["2"], result


def test_list_new_issues_http_error_returns_empty_list():
    def _get(*a, **k):
        return _FakeResponse(500, json_data=[])

    sentry_tools.requests.get = _get
    result = _with_fake_config(
        _FakeConfig(),
        lambda: list_new_issues("2026-07-01T00:00:00Z"),
    )
    assert result == [], result


# ---------------------------------------------------------------------------
# issue_summary — degraded / network
# ---------------------------------------------------------------------------

def test_issue_summary_degrades_without_credentials():
    result = _with_fake_config(
        _FakeConfig(project=None),
        issue_summary,
    )
    assert "not configured" in result, result


def test_issue_summary_success():
    def _get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(200, json_data=[RAW_ISSUE_OLD, RAW_ISSUE_NEW])

    sentry_tools.requests.get = _get
    result = _with_fake_config(_FakeConfig(), issue_summary)
    assert "2 unresolved issue(s)" in result, result


def test_issue_summary_error_returns_message_not_raise():
    def _get(*a, **k):
        raise requests.exceptions.ConnectionError("refused")

    sentry_tools.requests.get = _get
    result = _with_fake_config(_FakeConfig(), issue_summary)
    assert result == "Sentry: error fetching issue summary.", result


if __name__ == "__main__":
    tests = [
        test_parse_issue_maps_known_fields,
        test_parse_issue_falls_back_to_metadata_type_for_title,
        test_parse_issue_handles_missing_counts,
        test_filter_issues_since_keeps_only_recent,
        test_filter_issues_since_no_cutoff_returns_all,
        test_filter_issues_since_unparseable_cutoff_returns_all,
        test_filter_issues_since_missing_first_seen_is_kept,
        test_summarize_issues_aggregates_counts,
        test_summarize_issues_empty,
        test_format_issue_summary_no_issues,
        test_format_issue_summary_includes_counts_and_top_issues,
        test_list_new_issues_degrades_without_credentials,
        test_list_new_issues_missing_org_degrades,
        test_list_new_issues_success,
        test_list_new_issues_http_error_returns_empty_list,
        test_issue_summary_degrades_without_credentials,
        test_issue_summary_success,
        test_issue_summary_error_returns_message_not_raise,
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
