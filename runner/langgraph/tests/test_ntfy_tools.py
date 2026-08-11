"""Tests for tools/ntfy_tools.py — phone push via ntfy.sh."""
import pytest
from unittest.mock import MagicMock, patch

from tools.ntfy_tools import (
    send_phone_push,
    notify_phone_event,
    _build_push_message,
    PHONE_PUSH_EVENTS,
)


# ---------------------------------------------------------------------------
# PHONE_PUSH_EVENTS set
# ---------------------------------------------------------------------------

def test_phone_push_events_contains_resource_request():
    assert "resource_request_pending" in PHONE_PUSH_EVENTS


def test_phone_push_events_contains_batch_request():
    assert "dependency_batch_request" in PHONE_PUSH_EVENTS


def test_phone_push_events_does_not_contain_task_completed():
    # task_completed must NOT reach the phone — it belongs in Slack only
    assert "task_completed" not in PHONE_PUSH_EVENTS


def test_phone_push_events_does_not_contain_error():
    assert "error" not in PHONE_PUSH_EVENTS


# ---------------------------------------------------------------------------
# _build_push_message — pure function, no I/O
# ---------------------------------------------------------------------------

def test_build_message_resource_request_basic():
    title, msg = _build_push_message("resource_request_pending", {
        "credentials": ["STRIPE_SECRET_KEY"],
        "resources": [],
    }, task_id="m4c-09")
    assert "m4c-09" in title
    assert "STRIPE_SECRET_KEY" in msg
    assert "1" in msg


def test_build_message_resource_request_no_task_id():
    title, msg = _build_push_message("resource_request_pending", {
        "credentials": ["A", "B"],
        "resources": ["some resource"],
    }, task_id=None)
    assert "[" not in title  # no task label
    assert "3" in msg  # 2 creds + 1 resource


def test_build_message_resource_request_caps_list_at_5():
    creds = [f"CRED_{i}" for i in range(10)]
    _, msg = _build_push_message("resource_request_pending", {"credentials": creds}, task_id=None)
    # Only the first 5 are shown
    assert "CRED_4" in msg
    assert "CRED_5" not in msg


def test_build_message_batch_request():
    title, msg = _build_push_message("dependency_batch_request", {"count": 7}, task_id=None)
    assert "7" in msg
    assert "dependency_batch_request" in title.lower() or "roadmap" in title.lower()


def test_build_message_unknown_event():
    title, msg = _build_push_message("some_other_event", {"key": "val"}, task_id=None)
    assert title == "some_other_event"


# ---------------------------------------------------------------------------
# send_phone_push — no NTFY_TOPIC → available: False
# ---------------------------------------------------------------------------

def test_send_phone_push_no_topic(monkeypatch):
    monkeypatch.setattr("tools.ntfy_tools._topic", lambda: "")
    result = send_phone_push("title", "message")
    assert result["available"] is False
    assert "NTFY_TOPIC" in result.get("reason", "")


def test_send_phone_push_success(monkeypatch):
    monkeypatch.setattr("tools.ntfy_tools._topic", lambda: "test-topic")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = lambda: None
    with patch("tools.ntfy_tools.requests.post", return_value=mock_resp) as mock_post:
        result = send_phone_push("title", "message")
    assert result["available"] is True
    assert result["ok"] is True
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "test-topic" in call_kwargs[0][0]  # URL contains topic


def test_send_phone_push_http_error(monkeypatch):
    monkeypatch.setattr("tools.ntfy_tools._topic", lambda: "test-topic")
    with patch("tools.ntfy_tools.requests.post", side_effect=Exception("connection refused")):
        result = send_phone_push("title", "message")
    assert result["available"] is True
    assert result["ok"] is False
    assert "connection refused" in result.get("error", "")


def test_send_phone_push_sets_priority_header(monkeypatch):
    monkeypatch.setattr("tools.ntfy_tools._topic", lambda: "test-topic")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    with patch("tools.ntfy_tools.requests.post", return_value=mock_resp) as mock_post:
        send_phone_push("t", "m", priority=5)
    headers = mock_post.call_args[1]["headers"]
    assert headers["Priority"] == "5"


# ---------------------------------------------------------------------------
# notify_phone_event — routing
# ---------------------------------------------------------------------------

def test_notify_phone_event_skips_non_phone_event(monkeypatch):
    monkeypatch.setattr("tools.ntfy_tools._topic", lambda: "test-topic")
    result = notify_phone_event("task_completed", {})
    assert result.get("skipped") is True


def test_notify_phone_event_fires_for_resource_request(monkeypatch):
    monkeypatch.setattr("tools.ntfy_tools._topic", lambda: "test-topic")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    with patch("tools.ntfy_tools.requests.post", return_value=mock_resp) as mock_post:
        result = notify_phone_event("resource_request_pending", {"credentials": ["X"]})
    assert mock_post.called
    assert result.get("ok") is True


def test_notify_phone_event_no_topic(monkeypatch):
    monkeypatch.setattr("tools.ntfy_tools._topic", lambda: "")
    result = notify_phone_event("resource_request_pending", {"credentials": ["X"]})
    assert result["available"] is False
