"""Tests for the M4c supervisory early-stop rules.

All five decision functions are pure (or injectable) and tested without
any network calls, model calls, or disk I/O.

Requirements verified:
  (a) CI environmental classification — same check on base/other PR → skip;
      only-on-branch → route to repair as today.
  (b) Auth failure detection — 401/403 halts with worker_auth_failed, never
      retried; 429 (cooldown) is NOT detected as auth; 5xx is NOT detected.
  (c) Check count stability — unstable count keeps polling; stable merges;
      required_checks anchor works on first all-complete poll.
  (d) PR gate reconciliation — mismatch reported; no change to either side;
      no required checks → no mismatch.
  (e) Spend-without-progress ceiling — stops with correct reason and figures;
      any merge prevents the stop; disabled means no-op.

Also verifies loop_watchdog integration:
  - worker_auth_failed and no_progress_for_spend are in HARD_GATE_REASONS.
  - Both cause should_restart=False.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.supervisory_early_stop import (
    classify_ci_failure_environmental,
    detect_worker_auth_failure,
    check_count_is_stable,
    reconcile_pr_gate_sets,
    evaluate_spend_without_progress,
    NO_PROGRESS_STOP,
)
from tools.loop_watchdog import HARD_GATE_REASONS, evaluate_restart_decision

_PASS = []
_FAIL = []


def _ok(name):
    _PASS.append(name)


def _err(name, exc):
    _FAIL.append((name, exc))
    traceback.print_exc()


def run(name, fn):
    try:
        fn()
        _ok(name)
    except Exception as exc:
        _err(name, exc)


# ---------------------------------------------------------------------------
# Helpers — injectable mock functions
# ---------------------------------------------------------------------------

def _conclusions_fn(*_args, **_kwargs):
    """Default: returns empty (no check data)."""
    return {}


def _prs_fn(*_args, **_kwargs):
    """Default: no open PRs."""
    return []


# ---------------------------------------------------------------------------
# (a) classify_ci_failure_environmental
# ---------------------------------------------------------------------------

def test_environmental_when_base_has_same_failure():
    """A check that also fails on the base commit → environmental."""
    def _base_conclusions(repo, sha, token):
        if sha == "basesha":
            return {"E2E (Playwright)": "failure", "Lint": "success"}
        return {}

    result = classify_ci_failure_environmental(
        failed_checks=["E2E (Playwright)"],
        repo="owner/repo",
        base_sha="basesha",
        token="tok",
        fetch_commit_check_conclusions_fn=_base_conclusions,
        list_open_pr_heads_fn=_prs_fn,
    )
    assert result["environmental"] is True, result
    assert any(c["branch"] == "base" for c in result["corroborating"]), result


run("ci_env: base_has_same_failure", test_environmental_when_base_has_same_failure)


def test_not_environmental_when_only_on_branch():
    """A check failing only on the PR branch → route to repair, not skip."""
    def _base_conclusions(repo, sha, token):
        if sha == "basesha":
            return {"E2E (Playwright)": "success"}  # green on base
        return {}

    result = classify_ci_failure_environmental(
        failed_checks=["E2E (Playwright)"],
        repo="owner/repo",
        base_sha="basesha",
        token="tok",
        fetch_commit_check_conclusions_fn=_base_conclusions,
        list_open_pr_heads_fn=_prs_fn,
    )
    assert result["environmental"] is False, result
    assert result["corroborating"] == [], result


run("ci_env: only_on_branch_routes_to_repair", test_not_environmental_when_only_on_branch)


def test_environmental_when_other_pr_has_same_failure():
    """A check also failing on another open PR → environmental."""
    def _pr_conclusions(repo, sha, token):
        if sha == "othersha":
            return {"E2E (Playwright)": "failure"}
        return {"E2E (Playwright)": "success"}  # base is green

    def _open_prs(repo, token, current_pr_number):
        return [{"sha": "othersha", "branch": "feature/other", "number": 55}]

    result = classify_ci_failure_environmental(
        failed_checks=["E2E (Playwright)"],
        repo="owner/repo",
        base_sha="basesha",
        token="tok",
        current_pr_number=42,
        fetch_commit_check_conclusions_fn=_pr_conclusions,
        list_open_pr_heads_fn=_open_prs,
    )
    assert result["environmental"] is True, result
    assert any(c.get("branch") == "feature/other" for c in result["corroborating"]), result


run("ci_env: other_pr_has_same_failure", test_environmental_when_other_pr_has_same_failure)


def test_environmental_disabled_returns_false():
    """When enabled=False, always returns environmental=False."""
    def _base_conclusions(repo, sha, token):
        return {"E2E (Playwright)": "failure"}

    result = classify_ci_failure_environmental(
        failed_checks=["E2E (Playwright)"],
        repo="owner/repo",
        base_sha="basesha",
        token="tok",
        enabled=False,
        fetch_commit_check_conclusions_fn=_base_conclusions,
    )
    assert result["environmental"] is False, result


run("ci_env: disabled_returns_false", test_environmental_disabled_returns_false)


def test_environmental_no_failed_checks_returns_false():
    """Empty failed_checks list → never environmental."""
    result = classify_ci_failure_environmental(
        failed_checks=[],
        repo="owner/repo",
        base_sha="basesha",
        token="tok",
    )
    assert result["environmental"] is False, result


run("ci_env: empty_failed_checks", test_environmental_no_failed_checks_returns_false)


# ---------------------------------------------------------------------------
# (b) detect_worker_auth_failure
# ---------------------------------------------------------------------------

def test_auth_401_in_json_detected():
    """api_error_status: 401 in output → auth_failed."""
    result = detect_worker_auth_failure(
        error='{"api_error_status": 401, "error": "Unauthorized"}',
        output="",
    )
    assert result["auth_failed"] is True, result
    assert "401" in result["pattern"], result


run("auth: 401_json_detected", test_auth_401_in_json_detected)


def test_auth_403_in_json_detected():
    """api_error_status: 403 → auth_failed."""
    result = detect_worker_auth_failure(
        error='{"api_error_status": 403, "error": "Forbidden"}',
        output="",
    )
    assert result["auth_failed"] is True, result


run("auth: 403_json_detected", test_auth_403_in_json_detected)


def test_auth_revoked_token_detected():
    """'OAuth access token has been revoked' → auth_failed."""
    result = detect_worker_auth_failure(
        error="api_error_status: 401, OAuth access token has been revoked",
        output="",
    )
    assert result["auth_failed"] is True, result


run("auth: revoked_token_detected", test_auth_revoked_token_detected)


def test_auth_failed_to_authenticate_detected():
    """'failed to authenticate' → auth_failed."""
    result = detect_worker_auth_failure(
        error="",
        output="Error: Failed to authenticate with the API",
    )
    assert result["auth_failed"] is True, result


run("auth: failed_to_authenticate", test_auth_failed_to_authenticate_detected)


def test_auth_429_not_detected_as_auth():
    """429 (rate limit / cooldown) must NOT be classified as an auth failure.

    The cooldown guard handles 429; classifying it as auth_failed would wrongly
    halt the loop instead of waiting for the quota window to reset.
    """
    result = detect_worker_auth_failure(
        error='{"api_error_status": 429, "error": "rate limit exceeded"}',
        output="claude usage limit reached, try again in 2 hours",
    )
    assert result["auth_failed"] is False, result


run("auth: 429_not_auth_failure", test_auth_429_not_detected_as_auth)


def test_auth_5xx_not_detected():
    """5xx (transient server error) must NOT be classified as auth failure."""
    result = detect_worker_auth_failure(
        error='{"api_error_status": 500, "error": "Internal server error"}',
        output="",
    )
    assert result["auth_failed"] is False, result


run("auth: 5xx_not_auth_failure", test_auth_5xx_not_detected)


def test_auth_clean_success_not_detected():
    """No error output at all → not an auth failure."""
    result = detect_worker_auth_failure(error="", output="Task completed successfully.")
    assert result["auth_failed"] is False, result


run("auth: clean_success_not_detected", test_auth_clean_success_not_detected)


# ---------------------------------------------------------------------------
# (c) check_count_is_stable
# ---------------------------------------------------------------------------

def test_stability_first_all_complete_poll_not_stable():
    """First all-complete poll with unknown prev → not stable yet."""
    assert check_count_is_stable(curr_total=3, prev_total=None, required_checks=None) is False


run("stability: first_poll_not_stable", test_stability_first_all_complete_poll_not_stable)


def test_stability_same_count_two_polls_stable():
    """Same count across two consecutive all-complete polls → stable."""
    assert check_count_is_stable(curr_total=3, prev_total=3, required_checks=None) is True


run("stability: same_count_two_polls", test_stability_same_count_two_polls_stable)


def test_stability_count_changed_between_polls_not_stable():
    """Count changed from previous poll → not stable."""
    assert check_count_is_stable(curr_total=5, prev_total=3, required_checks=None) is False


run("stability: count_changed_not_stable", test_stability_count_changed_between_polls_not_stable)


def test_stability_required_checks_anchor_matches():
    """Count matches required_checks → stable on first all-complete poll."""
    required = ["Lint", "Build", "Tests", "E2E", "Deploy Check"]
    assert check_count_is_stable(curr_total=5, prev_total=None, required_checks=required) is True


run("stability: required_checks_anchor_matches", test_stability_required_checks_anchor_matches)


def test_stability_required_checks_count_too_low():
    """Count less than required_checks and prev unknown → not stable."""
    required = ["Lint", "Build", "Tests", "E2E", "Deploy Check"]
    assert check_count_is_stable(curr_total=2, prev_total=None, required_checks=required) is False


run("stability: count_below_required", test_stability_required_checks_count_too_low)


def test_stability_zero_count_not_stable():
    """Zero checks registered → never stable."""
    assert check_count_is_stable(curr_total=0, prev_total=0, required_checks=None) is False


run("stability: zero_count_not_stable", test_stability_zero_count_not_stable)


def test_stability_count_exceeds_required():
    """More checks than required (advisory included) → stable."""
    required = ["Lint", "Build"]
    assert check_count_is_stable(curr_total=3, prev_total=None, required_checks=required) is True


run("stability: count_exceeds_required", test_stability_count_exceeds_required)


# ---------------------------------------------------------------------------
# (d) reconcile_pr_gate_sets
# ---------------------------------------------------------------------------

def test_reconcile_mismatch_when_required_is_non_blocking():
    """A check that the repo requires but the runner treats as non-blocking → mismatch."""
    result = reconcile_pr_gate_sets(
        non_blocking_substrings=["[informational]"],
        required_check_contexts=["E2E (Playwright) [informational]", "Lint"],
    )
    assert result["mismatch"] is True, result
    assert "E2E (Playwright) [informational]" in result["runner_ignores_repo_requires"], result


run("reconcile: required_is_non_blocking", test_reconcile_mismatch_when_required_is_non_blocking)


def test_reconcile_no_mismatch_when_sets_agree():
    """Required checks have no non-blocking substrings → no mismatch."""
    result = reconcile_pr_gate_sets(
        non_blocking_substrings=["[informational]"],
        required_check_contexts=["Lint", "Build", "Tests"],
    )
    assert result["mismatch"] is False, result
    assert result["runner_ignores_repo_requires"] == [], result


run("reconcile: no_mismatch_when_sets_agree", test_reconcile_no_mismatch_when_sets_agree)


def test_reconcile_no_required_checks_no_mismatch():
    """Empty required-checks list → no mismatch (branch protection off)."""
    result = reconcile_pr_gate_sets(
        non_blocking_substrings=["[informational]"],
        required_check_contexts=[],
    )
    assert result["mismatch"] is False, result


run("reconcile: no_required_checks", test_reconcile_no_required_checks_no_mismatch)


def test_reconcile_empty_non_blocking_no_mismatch():
    """Empty non-blocking list → no mismatch (runner strict as repo)."""
    result = reconcile_pr_gate_sets(
        non_blocking_substrings=[],
        required_check_contexts=["Lint", "Build"],
    )
    assert result["mismatch"] is False, result


run("reconcile: empty_non_blocking", test_reconcile_empty_non_blocking_no_mismatch)


def test_reconcile_does_not_modify_either_side():
    """reconcile_pr_gate_sets must never mutate its inputs."""
    non_blocking = ["[informational]"]
    required = ["E2E [informational]", "Lint"]
    _ = reconcile_pr_gate_sets(non_blocking, required)
    assert non_blocking == ["[informational]"], "non_blocking was mutated"
    assert required == ["E2E [informational]", "Lint"], "required was mutated"


run("reconcile: inputs_not_mutated", test_reconcile_does_not_modify_either_side)


def test_reconcile_case_insensitive():
    """Substring matching is case-insensitive."""
    result = reconcile_pr_gate_sets(
        non_blocking_substrings=["INFORMATIONAL"],
        required_check_contexts=["E2E (Playwright) [informational]"],
    )
    assert result["mismatch"] is True, result


run("reconcile: case_insensitive", test_reconcile_case_insensitive)


# ---------------------------------------------------------------------------
# (e) evaluate_spend_without_progress
# ---------------------------------------------------------------------------

def test_spend_no_ceiling_configured_no_stop():
    """Both ceilings at 0 (disabled) → ceiling_hit=False always."""
    result = evaluate_spend_without_progress(
        session_tokens=9_999_999,
        elapsed_minutes=999,
        merges_this_session=0,
        max_tokens=0,
        max_minutes=0,
    )
    assert result["ceiling_hit"] is False, result
    assert result["stop_reason"] is None, result


run("spend: no_ceiling_no_stop", test_spend_no_ceiling_configured_no_stop)


def test_spend_tokens_ceiling_exceeded_no_merges():
    """Token ceiling exceeded with zero merges → ceiling_hit=True."""
    result = evaluate_spend_without_progress(
        session_tokens=5_000_001,
        elapsed_minutes=10,
        merges_this_session=0,
        max_tokens=5_000_000,
        max_minutes=0,
    )
    assert result["ceiling_hit"] is True, result
    assert result["stop_reason"] == NO_PROGRESS_STOP, result
    assert "5,000,001" in result["report"] or "5000001" in result["report"], result


run("spend: tokens_exceeded_no_merges", test_spend_tokens_ceiling_exceeded_no_merges)


def test_spend_time_ceiling_exceeded_no_merges():
    """Time ceiling exceeded with zero merges → ceiling_hit=True."""
    result = evaluate_spend_without_progress(
        session_tokens=100,
        elapsed_minutes=121,
        merges_this_session=0,
        max_tokens=0,
        max_minutes=120,
    )
    assert result["ceiling_hit"] is True, result
    assert result["stop_reason"] == NO_PROGRESS_STOP, result


run("spend: time_exceeded_no_merges", test_spend_time_ceiling_exceeded_no_merges)


def test_spend_one_merge_prevents_stop():
    """Any successful merge → ceiling_hit=False even when over the token limit."""
    result = evaluate_spend_without_progress(
        session_tokens=10_000_000,
        elapsed_minutes=999,
        merges_this_session=1,
        max_tokens=5_000_000,
        max_minutes=60,
    )
    assert result["ceiling_hit"] is False, result


run("spend: one_merge_prevents_stop", test_spend_one_merge_prevents_stop)


def test_spend_below_ceiling_no_stop():
    """Under the ceiling with zero merges → no stop yet."""
    result = evaluate_spend_without_progress(
        session_tokens=4_999_999,
        elapsed_minutes=59,
        merges_this_session=0,
        max_tokens=5_000_000,
        max_minutes=60,
    )
    assert result["ceiling_hit"] is False, result


run("spend: below_ceiling_no_stop", test_spend_below_ceiling_no_stop)


def test_spend_disabled_no_stop():
    """enabled=False → always ceiling_hit=False."""
    result = evaluate_spend_without_progress(
        session_tokens=99_999_999,
        elapsed_minutes=9999,
        merges_this_session=0,
        max_tokens=1,
        max_minutes=1,
        enabled=False,
    )
    assert result["ceiling_hit"] is False, result


run("spend: disabled_no_stop", test_spend_disabled_no_stop)


def test_spend_report_includes_figures():
    """The report string includes tokens spent and merges achieved."""
    result = evaluate_spend_without_progress(
        session_tokens=4_367_840,
        elapsed_minutes=90,
        merges_this_session=0,
        max_tokens=4_000_000,
        max_minutes=0,
    )
    assert result["ceiling_hit"] is True, result
    assert "4,367,840" in result["report"] or "4367840" in result["report"], result["report"]
    assert "0" in result["report"], result["report"]


run("spend: report_includes_figures", test_spend_report_includes_figures)


# ---------------------------------------------------------------------------
# loop_watchdog integration
# ---------------------------------------------------------------------------

def test_worker_auth_failed_is_hard_gate():
    assert "worker_auth_failed" in HARD_GATE_REASONS


run("watchdog: worker_auth_failed_is_hard_gate", test_worker_auth_failed_is_hard_gate)


def test_no_progress_for_spend_is_hard_gate():
    assert "no_progress_for_spend" in HARD_GATE_REASONS


run("watchdog: no_progress_for_spend_is_hard_gate", test_no_progress_for_spend_is_hard_gate)


def test_worker_auth_failed_does_not_restart():
    r = evaluate_restart_decision("worker_auth_failed")
    assert r["should_restart"] is False


run("watchdog: worker_auth_failed_no_restart", test_worker_auth_failed_does_not_restart)


def test_no_progress_for_spend_does_not_restart():
    r = evaluate_restart_decision("no_progress_for_spend")
    assert r["should_restart"] is False


run("watchdog: no_progress_for_spend_no_restart", test_no_progress_for_spend_does_not_restart)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

print(f"\nRan {len(_PASS) + len(_FAIL)} test(s): {len(_PASS)} passed, {len(_FAIL)} failed.")
if _FAIL:
    print("FAILED tests:")
    for name, exc in _FAIL:
        print(f"  {name}: {exc}")
    raise SystemExit(1)
else:
    print("All tests passed.")
