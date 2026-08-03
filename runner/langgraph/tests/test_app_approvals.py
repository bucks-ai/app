"""Unit tests for tools.app_approvals — pure classification<->row<->inbox mapping.

Runs standalone (no pytest dependency), mirroring tests/test_slack_approvals.py:

    python tests/test_app_approvals.py

No Supabase calls anywhere: this module (and app_approvals_daemon.py's use of
it) never touches the network from these tests.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.slack_approvals import classify_outbox_file
from tools.app_approvals import (
    classification_to_row,
    decision_to_inbox_write,
    is_already_decided,
    needs_inbox_sync,
)

OWNER = "11111111-1111-1111-1111-111111111111"


# ---------------------------------------------------------------------------
# classification_to_row — one per approval type
# ---------------------------------------------------------------------------

def test_classification_to_row_merge_approval():
    c = classify_outbox_file("task_123_merge_approval_request.txt")
    row = classification_to_row(c, OWNER, "task_123_merge_approval_request.txt", "risk: HIGH")
    assert row["user_id"] == OWNER
    assert row["request_type"] == "merge_approval"
    assert row["request_id"] == "task_123"
    assert row["source_file"] == "task_123_merge_approval_request.txt"
    assert row["title"] == "Merge Approval Required"
    assert row["body"] == "risk: HIGH"
    assert row["status"] == "pending"


def test_classification_to_row_sql_approval():
    c = classify_outbox_file("task_123_sql_approval.sql")
    row = classification_to_row(c, OWNER, "task_123_sql_approval.sql", "CREATE TABLE x (id int);")
    assert row["request_type"] == "sql_approval"
    assert row["request_id"] == "task_123"
    assert row["title"] == "SQL Approval Required"
    assert row["status"] == "pending"


def test_classification_to_row_resource_request():
    c = classify_outbox_file("task_123_resource_request.txt")
    row = classification_to_row(c, OWNER, "task_123_resource_request.txt", "need STRIPE_KEY")
    assert row["request_type"] == "resource_request"
    assert row["title"] == "Resource / Credential Request"


def test_classification_to_row_strategic_review():
    c = classify_outbox_file("strategic_review_7.txt")
    row = classification_to_row(c, OWNER, "strategic_review_7.txt", "checkpoint notes")
    assert row["request_type"] == "strategic_review"
    assert row["request_id"] == "7"
    assert row["title"] == "Strategic Review Checkpoint"


def test_classification_to_row_sanitizes_and_truncates_body():
    c = classify_outbox_file("task_1_resource_request.txt")
    row = classification_to_row(c, OWNER, "task_1_resource_request.txt", "token=abcdefghijklmnop123")
    assert "abcdefghijklmnop123" not in row["body"]
    assert "[REDACTED]" in row["body"]


def test_classification_to_row_requires_user_id():
    c = classify_outbox_file("task_1_merge_approval_request.txt")
    try:
        classification_to_row(c, "", "task_1_merge_approval_request.txt", "body")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_classification_to_row_unknown_type_raises():
    try:
        classification_to_row({"request_type": "bogus", "request_id": "t1"}, OWNER, "f.txt", "body")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# decision_to_inbox_write — pending / approved / rejected, per type
# ---------------------------------------------------------------------------

def test_decision_pending_is_noop():
    row = {"request_type": "merge_approval", "request_id": "t1", "status": "pending"}
    d = decision_to_inbox_write(row)
    assert d == {"should_write": False, "inbox_filename": None, "content": None, "outcome": None}


def test_decision_approved_merge_approval():
    row = {"request_type": "merge_approval", "request_id": "t1", "status": "approved"}
    d = decision_to_inbox_write(row)
    assert d["should_write"] is True
    assert d["inbox_filename"] == "t1_merge_approved.txt"
    assert d["outcome"] == "approved"


def test_decision_approved_sql_approval_writes_approved_content():
    row = {"request_type": "sql_approval", "request_id": "t1", "status": "approved"}
    d = decision_to_inbox_write(row)
    assert d["content"].strip().lower() == "approved"


def test_decision_rejected_sql_approval_writes_rejected_content():
    row = {"request_type": "sql_approval", "request_id": "t1", "status": "rejected"}
    d = decision_to_inbox_write(row)
    assert d["should_write"] is True
    assert d["content"].strip().lower() == "rejected"
    assert d["outcome"] == "rejected"


def test_decision_rejected_merge_approval_writes_nothing():
    row = {"request_type": "merge_approval", "request_id": "t1", "status": "rejected"}
    d = decision_to_inbox_write(row)
    assert d["should_write"] is False
    assert d["outcome"] == "rejected_no_file"


def test_decision_rejected_resource_request_writes_nothing():
    row = {"request_type": "resource_request", "request_id": "t1", "status": "rejected"}
    d = decision_to_inbox_write(row)
    assert d["should_write"] is False


def test_decision_rejected_strategic_review_writes_nothing():
    row = {"request_type": "strategic_review", "request_id": "5", "status": "rejected"}
    d = decision_to_inbox_write(row)
    assert d["should_write"] is False


def test_decision_unknown_status_raises():
    row = {"request_type": "merge_approval", "request_id": "t1", "status": "bogus"}
    try:
        decision_to_inbox_write(row)
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# is_already_decided / needs_inbox_sync
# ---------------------------------------------------------------------------

def test_is_already_decided():
    assert is_already_decided({"status": "pending"}) is False
    assert is_already_decided({"status": "approved"}) is True
    assert is_already_decided({"status": "rejected"}) is True


def test_needs_inbox_sync_true_when_decided_and_unsynced():
    row = {"status": "approved", "inbox_synced_at": None}
    assert needs_inbox_sync(row) is True


def test_needs_inbox_sync_false_when_already_synced():
    row = {"status": "approved", "inbox_synced_at": "2026-01-01T00:00:00Z"}
    assert needs_inbox_sync(row) is False


def test_needs_inbox_sync_false_when_still_pending():
    row = {"status": "pending", "inbox_synced_at": None}
    assert needs_inbox_sync(row) is False


if __name__ == "__main__":
    tests = [
        test_classification_to_row_merge_approval,
        test_classification_to_row_sql_approval,
        test_classification_to_row_resource_request,
        test_classification_to_row_strategic_review,
        test_classification_to_row_sanitizes_and_truncates_body,
        test_classification_to_row_requires_user_id,
        test_classification_to_row_unknown_type_raises,
        test_decision_pending_is_noop,
        test_decision_approved_merge_approval,
        test_decision_approved_sql_approval_writes_approved_content,
        test_decision_rejected_sql_approval_writes_rejected_content,
        test_decision_rejected_merge_approval_writes_nothing,
        test_decision_rejected_resource_request_writes_nothing,
        test_decision_rejected_strategic_review_writes_nothing,
        test_decision_unknown_status_raises,
        test_is_already_decided,
        test_needs_inbox_sync_true_when_decided_and_unsynced,
        test_needs_inbox_sync_false_when_already_synced,
        test_needs_inbox_sync_false_when_still_pending,
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
