"""Unit tests for tools.slack_tools and its flight-recorder wiring.

Runs standalone (no pytest dependency), mirroring the other test modules:

    python tests/test_slack_tools.py

No network is hit: requests.post / post_message are stubbed throughout.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from config import get_config
import tools.slack_tools as slack
import tools.log_tools as log_tools


def _cfg():
    """Fresh config so env/attr tweaks in one test don't leak into others."""
    config._config = None
    return get_config()


# ---------------------------------------------------------------------------
# format_event — pure rendering
# ---------------------------------------------------------------------------

def test_format_event_includes_type_and_task():
    text = slack.format_event("task_completed", {}, task_id="t1")
    assert "task_completed" in text
    assert "t1" in text


def test_format_event_renders_error_detail():
    text = slack.format_event("error", {"error": "boom"}, task_id="t1")
    assert "boom" in text


def test_format_event_loop_blocked_detail():
    text = slack.format_event(
        "loop_blocked_on_deploy", {"reason": "deploy_failed", "state": "ERROR"}
    )
    assert "deploy_failed" in text and "ERROR" in text


def test_format_event_sql_blocked_lists_terms():
    text = slack.format_event("sql_scan_blocked", {"scan": {"blocked_terms": ["DROP TABLE"]}})
    assert "DROP TABLE" in text


def test_format_event_generic_fallback():
    # Unknown event still renders without raising, skipping nested values.
    text = slack.format_event("mystery_event", {"a": 1, "nested": {"x": 2}})
    assert "mystery_event" in text and "a: 1" in text and "nested" not in text


# ---------------------------------------------------------------------------
# notify_event — filtering / degradation
# ---------------------------------------------------------------------------

def test_notify_skips_when_no_webhook():
    cfg = _cfg()
    cfg.slack_webhook_url = None
    cfg.slack_notify = True
    res = slack.notify_event("task_completed", {}, "t1")
    assert res["available"] is False


def test_notify_skips_when_disabled():
    cfg = _cfg()
    cfg.slack_webhook_url = "https://hooks.slack.test/x"
    cfg.slack_notify = False
    res = slack.notify_event("task_completed", {}, "t1")
    assert res["available"] is False


def test_notify_skips_non_notable_event():
    cfg = _cfg()
    cfg.slack_webhook_url = "https://hooks.slack.test/x"
    cfg.slack_notify = True
    posted = []
    orig = slack.post_message
    slack.post_message = lambda *a, **k: posted.append(a) or {"ok": True}
    try:
        res = slack.notify_event("deploy_poll_tick", {"poll": 1}, "t1")
    finally:
        slack.post_message = orig
    assert res.get("skipped") is True
    assert posted == [], "non-notable event must not post"


def test_notify_posts_notable_event():
    cfg = _cfg()
    cfg.slack_webhook_url = "https://hooks.slack.test/x"
    cfg.slack_notify = True
    posted = []
    orig = slack.post_message

    def _capture(text, blocks=None):
        posted.append(text)
        return {"available": True, "ok": True}

    slack.post_message = _capture
    try:
        res = slack.notify_event("task_completed", {}, "t1")
    finally:
        slack.post_message = orig
    assert res["ok"] is True
    assert len(posted) == 1 and "task_completed" in posted[0]


# ---------------------------------------------------------------------------
# post_message — webhook POST and graceful failure
# ---------------------------------------------------------------------------

def test_post_message_degrades_without_webhook():
    cfg = _cfg()
    cfg.slack_webhook_url = None
    res = slack.post_message("hi")
    assert res == {"available": False, "reason": "no SLACK_WEBHOOK_URL"}


def test_post_message_posts_payload():
    cfg = _cfg()
    cfg.slack_webhook_url = "https://hooks.slack.test/x"
    calls = []

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

    orig = slack.requests.post
    slack.requests.post = lambda url, json=None, timeout=None: calls.append((url, json)) or _Resp()
    try:
        res = slack.post_message("hello")
    finally:
        slack.requests.post = orig
    assert res["ok"] is True and res["status_code"] == 200
    assert calls[0][0] == "https://hooks.slack.test/x"
    assert calls[0][1]["text"] == "hello"


def test_post_message_swallows_network_error():
    cfg = _cfg()
    cfg.slack_webhook_url = "https://hooks.slack.test/x"

    def _boom(*a, **k):
        raise RuntimeError("connection refused")

    orig_post = slack.requests.post
    orig_log = slack.log_event
    logged = []
    slack.requests.post = _boom
    slack.log_event = lambda et, payload, task_id=None: logged.append(et)
    try:
        res = slack.post_message("hello")
    finally:
        slack.requests.post = orig_post
        slack.log_event = orig_log
    assert res["ok"] is False and "connection refused" in res["error"]
    assert "slack_degraded" in logged


# ---------------------------------------------------------------------------
# log_event wiring — every event fans out to Slack, failures are swallowed
# ---------------------------------------------------------------------------

def test_log_event_notifies_slack():
    seen = []
    orig = slack.notify_event
    # log_tools imports notify_event lazily, so patching the module attribute works.
    slack.notify_event = lambda et, payload, task_id=None: seen.append((et, task_id))
    orig_append = log_tools.append_jsonl_event
    log_tools.append_jsonl_event = lambda event: None  # silence disk I/O
    try:
        log_tools.log_event("task_completed", {"x": 1}, task_id="t9")
    finally:
        slack.notify_event = orig
        log_tools.append_jsonl_event = orig_append
    assert seen == [("task_completed", "t9")]


def test_log_event_survives_slack_failure():
    orig = slack.notify_event

    def _boom(*a, **k):
        raise RuntimeError("slack down")

    slack.notify_event = _boom
    orig_append = log_tools.append_jsonl_event
    log_tools.append_jsonl_event = lambda event: None
    try:
        event = log_tools.log_event("error", {"error": "x"})
    finally:
        slack.notify_event = orig
        log_tools.append_jsonl_event = orig_append
    assert event["event_type"] == "error", "log_event must return normally despite Slack error"


if __name__ == "__main__":
    tests = [
        test_format_event_includes_type_and_task,
        test_format_event_renders_error_detail,
        test_format_event_loop_blocked_detail,
        test_format_event_sql_blocked_lists_terms,
        test_format_event_generic_fallback,
        test_notify_skips_when_no_webhook,
        test_notify_skips_when_disabled,
        test_notify_skips_non_notable_event,
        test_notify_posts_notable_event,
        test_post_message_degrades_without_webhook,
        test_post_message_posts_payload,
        test_post_message_swallows_network_error,
        test_log_event_notifies_slack,
        test_log_event_survives_slack_failure,
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
