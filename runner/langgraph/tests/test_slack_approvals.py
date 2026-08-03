"""Unit tests for tools.slack_approvals — pure request<->Slack mapping logic.

Runs standalone (no pytest dependency), mirroring the other test modules:

    python tests/test_slack_approvals.py

No Slack calls anywhere: this module (and approvals_daemon.py's use of it)
never touches the network from these tests. One test per approval type in
both directions (outbox filename -> classification, button click -> inbox
file), plus malformed-payload rejection.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.slack_approvals import (
    classify_outbox_file,
    inbox_filename_for,
    supports_reject_file,
    sanitize_excerpt,
    truncate,
    build_approval_blocks,
    build_result_blocks,
    resolve_action,
    parse_button_value,
)


# ---------------------------------------------------------------------------
# classify_outbox_file — one per approval type, plus a non-match
# ---------------------------------------------------------------------------

def test_classify_merge_approval():
    c = classify_outbox_file("task_123_merge_approval_request.txt")
    assert c["request_type"] == "merge_approval"
    assert c["request_id"] == "task_123"
    assert c["inbox_filename"] == "task_123_merge_approved.txt"
    assert c["supports_reject_file"] is False


def test_classify_sql_approval():
    c = classify_outbox_file("task_123_sql_approval.sql")
    assert c["request_type"] == "sql_approval"
    assert c["request_id"] == "task_123"
    assert c["inbox_filename"] == "task_123_sql_approved.txt"
    assert c["supports_reject_file"] is True


def test_classify_resource_request():
    c = classify_outbox_file("task_123_resource_request.txt")
    assert c["request_type"] == "resource_request"
    assert c["request_id"] == "task_123"
    assert c["inbox_filename"] == "task_123_resources_provided.txt"
    assert c["supports_reject_file"] is False


def test_classify_strategic_review():
    c = classify_outbox_file("strategic_review_7.txt")
    assert c["request_type"] == "strategic_review"
    assert c["request_id"] == "7"
    assert c["inbox_filename"] == "strategic_review_7_approved.txt"
    assert c["supports_reject_file"] is False


def test_classify_non_approval_file_returns_none():
    assert classify_outbox_file("1_prompt.txt") is None
    assert classify_outbox_file("launch_readiness_scorecard.txt") is None
    assert classify_outbox_file("phase-7-browser-smoke.png") is None


def test_classify_task_id_with_underscores():
    c = classify_outbox_file("runner-mcp-connector-registry-repair_merge_approval_request.txt")
    assert c["request_type"] == "merge_approval"
    assert c["request_id"] == "runner-mcp-connector-registry-repair"


# ---------------------------------------------------------------------------
# inbox_filename_for / supports_reject_file
# ---------------------------------------------------------------------------

def test_inbox_filename_for_all_types():
    assert inbox_filename_for("merge_approval", "t1") == "t1_merge_approved.txt"
    assert inbox_filename_for("sql_approval", "t1") == "t1_sql_approved.txt"
    assert inbox_filename_for("resource_request", "t1") == "t1_resources_provided.txt"
    assert inbox_filename_for("strategic_review", "5") == "strategic_review_5_approved.txt"


def test_inbox_filename_for_unknown_type_raises():
    try:
        inbox_filename_for("bogus_type", "t1")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_supports_reject_file_only_sql_approval():
    assert supports_reject_file("sql_approval") is True
    assert supports_reject_file("merge_approval") is False
    assert supports_reject_file("resource_request") is False
    assert supports_reject_file("strategic_review") is False


# ---------------------------------------------------------------------------
# sanitize_excerpt / truncate
# ---------------------------------------------------------------------------

def test_sanitize_redacts_connection_strings():
    text = "DATABASE_URL=postgres://user:hunter2@db.example.com:5432/prod"
    out = sanitize_excerpt(text)
    assert "hunter2" not in out
    assert "[REDACTED]" in out


def test_sanitize_redacts_key_value_secrets():
    out = sanitize_excerpt("STRIPE_API_KEY: sk_live_abcdef1234567890")
    assert "sk_live_abcdef1234567890" not in out


def test_sanitize_passes_through_clean_text():
    text = "CREATE TABLE foo (id int);"
    assert sanitize_excerpt(text) == text


def test_truncate_short_text_unchanged():
    assert truncate("hello") == "hello"


def test_truncate_long_text_is_cut_and_marked():
    text = "x" * 2000
    out = truncate(text)
    assert len(out) < 2000
    assert "truncated" in out


# ---------------------------------------------------------------------------
# resolve_action — approve/reject per type
# ---------------------------------------------------------------------------

def test_resolve_approve_merge_approval():
    d = resolve_action("merge_approval", "t1", "approve")
    assert d["should_write"] is True
    assert d["inbox_filename"] == "t1_merge_approved.txt"
    assert d["outcome"] == "approved"


def test_resolve_approve_sql_approval():
    d = resolve_action("sql_approval", "t1", "approve")
    assert d["should_write"] is True
    assert d["content"].strip().lower() == "approved"
    assert d["outcome"] == "approved"


def test_resolve_reject_sql_approval_writes_rejected_content():
    d = resolve_action("sql_approval", "t1", "reject")
    assert d["should_write"] is True
    assert d["content"].strip().lower() == "rejected"
    assert d["outcome"] == "rejected"


def test_resolve_reject_merge_approval_writes_nothing():
    d = resolve_action("merge_approval", "t1", "reject")
    assert d["should_write"] is False
    assert d["content"] is None
    assert d["outcome"] == "rejected_no_file"


def test_resolve_reject_resource_request_writes_nothing():
    d = resolve_action("resource_request", "t1", "reject")
    assert d["should_write"] is False
    assert d["outcome"] == "rejected_no_file"


def test_resolve_reject_strategic_review_writes_nothing():
    d = resolve_action("strategic_review", "5", "reject")
    assert d["should_write"] is False
    assert d["outcome"] == "rejected_no_file"


def test_resolve_unknown_type_raises():
    try:
        resolve_action("bogus", "t1", "approve")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_resolve_unknown_action_raises():
    try:
        resolve_action("merge_approval", "t1", "maybe")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# build_approval_blocks / build_result_blocks — shape checks
# ---------------------------------------------------------------------------

def test_build_approval_blocks_has_approve_and_reject_buttons():
    blocks = build_approval_blocks("merge_approval", "t1", "t1_merge_approval_request.txt", "risk: HIGH")
    actions = [b for b in blocks if b.get("type") == "actions"][0]
    action_ids = [el["action_id"] for el in actions["elements"]]
    assert "runner_approve" in action_ids
    assert "runner_reject" in action_ids


def test_build_approval_blocks_button_value_roundtrips():
    blocks = build_approval_blocks("sql_approval", "t1", "t1_sql_approval.sql", "CREATE TABLE x (id int);")
    actions = [b for b in blocks if b.get("type") == "actions"][0]
    for el in actions["elements"]:
        parsed = parse_button_value(el["value"])
        assert parsed == {"request_type": "sql_approval", "request_id": "t1"}


def test_build_approval_blocks_sanitizes_body():
    blocks = build_approval_blocks("resource_request", "t1", "t1_resource_request.txt", "token=abcdefghijklmnop123")
    text_blob = " ".join(
        b["text"]["text"] for b in blocks if b.get("type") == "section"
    )
    assert "abcdefghijklmnop123" not in text_blob


def test_build_approval_blocks_unknown_type_raises():
    try:
        build_approval_blocks("bogus", "t1", "f.txt", "body")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_result_blocks_includes_actor_and_outcome():
    blocks = build_result_blocks("merge_approval", "t1", "approved", "arnav")
    text_blob = " ".join(b["text"]["text"] for b in blocks)
    assert "arnav" in text_blob
    assert "Approved" in text_blob


# ---------------------------------------------------------------------------
# parse_button_value — malformed payload rejection
# ---------------------------------------------------------------------------

def test_parse_button_value_rejects_invalid_json():
    try:
        parse_button_value("{not json")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_parse_button_value_rejects_non_object_json():
    try:
        parse_button_value("[1, 2, 3]")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_parse_button_value_rejects_unknown_request_type():
    try:
        parse_button_value('{"request_type": "bogus", "request_id": "t1"}')
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_parse_button_value_rejects_missing_request_id():
    try:
        parse_button_value('{"request_type": "merge_approval"}')
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_parse_button_value_rejects_non_string_request_id():
    try:
        parse_button_value('{"request_type": "merge_approval", "request_id": 123}')
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_parse_button_value_rejects_none():
    try:
        parse_button_value(None)
        assert False, "expected ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    tests = [
        test_classify_merge_approval,
        test_classify_sql_approval,
        test_classify_resource_request,
        test_classify_strategic_review,
        test_classify_non_approval_file_returns_none,
        test_classify_task_id_with_underscores,
        test_inbox_filename_for_all_types,
        test_inbox_filename_for_unknown_type_raises,
        test_supports_reject_file_only_sql_approval,
        test_sanitize_redacts_connection_strings,
        test_sanitize_redacts_key_value_secrets,
        test_sanitize_passes_through_clean_text,
        test_truncate_short_text_unchanged,
        test_truncate_long_text_is_cut_and_marked,
        test_resolve_approve_merge_approval,
        test_resolve_approve_sql_approval,
        test_resolve_reject_sql_approval_writes_rejected_content,
        test_resolve_reject_merge_approval_writes_nothing,
        test_resolve_reject_resource_request_writes_nothing,
        test_resolve_reject_strategic_review_writes_nothing,
        test_resolve_unknown_type_raises,
        test_resolve_unknown_action_raises,
        test_build_approval_blocks_has_approve_and_reject_buttons,
        test_build_approval_blocks_button_value_roundtrips,
        test_build_approval_blocks_sanitizes_body,
        test_build_approval_blocks_unknown_type_raises,
        test_build_result_blocks_includes_actor_and_outcome,
        test_parse_button_value_rejects_invalid_json,
        test_parse_button_value_rejects_non_object_json,
        test_parse_button_value_rejects_unknown_request_type,
        test_parse_button_value_rejects_missing_request_id,
        test_parse_button_value_rejects_non_string_request_id,
        test_parse_button_value_rejects_none,
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
