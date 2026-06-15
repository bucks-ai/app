"""Unit tests for rollback/revert deployment recovery policy.

Runs standalone:

    python tests/test_rollback_revert_policy.py
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.rollback_revert_policy import (
    deploy_failure_reason,
    evaluate_rollback_revert_policy,
    format_recovery_plan,
    normalize_policy,
)


def _failed_deploy():
    return {
        "success": False,
        "poll": {
            "ready": False,
            "terminal": True,
            "timed_out": False,
            "state": "ERROR",
            "deployment": {"uid": "dpl_123", "url": "example.vercel.app"},
        },
    }


def test_normalizes_policy_values():
    assert normalize_policy(None) == "manual"
    assert normalize_policy("rollback-then-revert") == "rollback_then_revert"
    assert normalize_policy("off") == "disabled"
    assert normalize_policy("surprise") == "manual"


def test_detects_failed_and_timed_out_deployments():
    assert deploy_failure_reason(_failed_deploy()) == "deploy_failed"
    assert deploy_failure_reason({"poll": {"timed_out": True}}) == "deploy_timed_out"
    assert deploy_failure_reason({"poll": {"ready": True, "terminal": True}}) is None
    assert deploy_failure_reason({"poll": {}}) is None


def test_manual_policy_requires_operator_plan():
    decision = evaluate_rollback_revert_policy(
        deploy_result=_failed_deploy(),
        policy="manual",
        task={"id": "t1", "title": "Demo", "branch": "feature/t1"},
        commit_sha="abc123",
    )

    assert decision["required"] is True, decision
    assert decision["status"] == "manual_required", decision
    assert decision["recommended_action"] == "manual_review", decision
    assert decision["deployment_id"] == "dpl_123", decision


def test_rollback_then_revert_policy_recommends_both_actions():
    decision = evaluate_rollback_revert_policy(
        deploy_result=_failed_deploy(),
        policy="rollback_then_revert",
        task={"id": "t1"},
        commit_sha="abc123",
    )

    assert decision["recommended_action"] == "rollback_deployment_then_revert_commit", decision


def test_disabled_policy_skips_plan():
    decision = evaluate_rollback_revert_policy(
        deploy_result=_failed_deploy(),
        policy="disabled",
        task={"id": "t1"},
        commit_sha="abc123",
    )

    assert decision["required"] is False, decision
    assert decision["status"] == "disabled", decision


def test_non_terminal_deploy_skips_plan():
    decision = evaluate_rollback_revert_policy(
        deploy_result={"success": False, "poll": {}},
        policy="manual",
        task={"id": "t1"},
        commit_sha="abc123",
    )

    assert decision["required"] is False, decision
    assert decision["reason"] == "no_terminal_deploy_failure", decision


def test_format_recovery_plan_includes_operator_steps():
    decision = evaluate_rollback_revert_policy(
        deploy_result=_failed_deploy(),
        policy="revert",
        task={"id": "t1", "title": "Demo"},
        commit_sha=None,
    )

    text = format_recovery_plan(decision)

    assert "Rollback / Revert Recovery Plan" in text
    assert "Recommended action: revert_commit" in text
    assert "No landed commit SHA was recorded" in text


if __name__ == "__main__":
    tests = [
        test_normalizes_policy_values,
        test_detects_failed_and_timed_out_deployments,
        test_manual_policy_requires_operator_plan,
        test_rollback_then_revert_policy_recommends_both_actions,
        test_disabled_policy_skips_plan,
        test_non_terminal_deploy_skips_plan,
        test_format_recovery_plan_includes_operator_steps,
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
