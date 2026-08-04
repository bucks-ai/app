"""Unit tests for the timeout ordering invariants.

Runs standalone (no pytest dependency):

    python tests/test_config_invariants.py

Covers ``check_threshold_invariants()`` and ``format_violations()`` in
``tools/config_invariants.py``, plus the assertion that the *shipped* defaults
in ``config.py`` satisfy every invariant — a regression here means the runner
would refuse to start out of the box.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.config_invariants import check_threshold_invariants, format_violations


# A snapshot that satisfies every invariant, used as the base for each test so
# a single flipped key isolates exactly one violation.
HEALTHY = {
    "claude_cli_timeout_s": 2400,
    "worker_timeout_threshold": 2700,
    "max_stale_task_minutes": 120,
    "stale_run_warn_minutes": 75,
    "max_runtime_minutes": 480,
    "pr_checks_empty_grace_s": 120,
    "pr_checks_timeout_s": 1200,
    "failure_retry_backoff_max_s": 300.0,
    "max_task_attempts": 3,
}


def _snapshot(**overrides):
    snap = dict(HEALTHY)
    snap.update(overrides)
    return snap


def _invariants(violations):
    return [v["invariant"] for v in violations]


def _assert_violates(snapshot, needle):
    violations = check_threshold_invariants(snapshot)
    matched = [v for v in violations if needle in v["invariant"]]
    assert matched, f"expected a violation matching {needle!r}, got {_invariants(violations)}"
    return matched[0]


# ---------------------------------------------------------------------------
# Healthy configuration
# ---------------------------------------------------------------------------

def test_healthy_snapshot_has_no_violations():
    assert check_threshold_invariants(HEALTHY) == []


def test_shipped_defaults_satisfy_every_invariant():
    """The defaults in config.py must start cleanly with no .env at all."""
    from config import RunnerConfig

    saved = {v.upper(): os.environ.pop(v.upper(), None) for v in HEALTHY}
    try:
        violations = RunnerConfig().threshold_violations()
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value
    assert violations == [], (
        "shipped config.py defaults violate an invariant: "
        f"{_invariants(violations)}"
    )


def test_shipped_profiles_satisfy_every_invariant():
    """The overnight profiles are copied verbatim to .env, so an inverted pair
    in one of them means an unattended run refuses to start at 2am."""
    from pathlib import Path

    from config import RunnerConfig

    profiles = sorted((Path(__file__).parent.parent / "profiles").glob("*.env"))
    assert profiles, "no profiles found to validate"

    for profile in profiles:
        overrides = {}
        for line in profile.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            overrides[key.strip()] = value.strip()

        saved = {k: os.environ.get(k) for k in overrides}
        try:
            for key, value in overrides.items():
                if value:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
            violations = RunnerConfig().threshold_violations()
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        assert violations == [], (
            f"{profile.name} violates an invariant: {_invariants(violations)}"
        )


def test_empty_snapshot_is_not_a_violation():
    """A partial snapshot must not manufacture violations out of missing keys."""
    assert check_threshold_invariants({}) == []


def test_non_numeric_values_are_skipped():
    assert check_threshold_invariants(
        _snapshot(worker_timeout_threshold=None, claude_cli_timeout_s="1800")
    ) == []


# ---------------------------------------------------------------------------
# Invariant 1 — CLAUDE_CLI_TIMEOUT_S < WORKER_TIMEOUT_THRESHOLD
# ---------------------------------------------------------------------------

def test_cli_timeout_above_guard_violates():
    v = _assert_violates(
        _snapshot(claude_cli_timeout_s=2400, worker_timeout_threshold=570),
        "CLAUDE_CLI_TIMEOUT_S < WORKER_TIMEOUT_THRESHOLD",
    )
    assert "WORKER_TIMEOUT_THRESHOLD=2700" in v["fix"]


def test_pre_m4c0_defaults_are_caught():
    """The exact defaults that shipped before this calibration must fail."""
    violations = check_threshold_invariants(_snapshot(
        claude_cli_timeout_s=1800,
        worker_timeout_threshold=570,
        max_stale_task_minutes=60,
        stale_run_warn_minutes=30,
    ))
    assert "CLAUDE_CLI_TIMEOUT_S < WORKER_TIMEOUT_THRESHOLD" in _invariants(violations)


def test_cli_timeout_equal_to_guard_violates():
    """Equality is a violation: at the boundary the guard fires on the kill."""
    _assert_violates(
        _snapshot(claude_cli_timeout_s=2700, worker_timeout_threshold=2700),
        "CLAUDE_CLI_TIMEOUT_S < WORKER_TIMEOUT_THRESHOLD",
    )


def test_guard_disabled_by_zero_is_not_a_violation():
    """WORKER_TIMEOUT_THRESHOLD=0 disables the guard — nothing to order."""
    violations = check_threshold_invariants(_snapshot(worker_timeout_threshold=0))
    assert "CLAUDE_CLI_TIMEOUT_S < WORKER_TIMEOUT_THRESHOLD" not in _invariants(violations)


# ---------------------------------------------------------------------------
# Invariant 2 — WORKER_TIMEOUT_THRESHOLD < MAX_STALE_TASK_MINUTES * 60
# ---------------------------------------------------------------------------

def test_watchdog_below_worker_guard_violates():
    _assert_violates(
        _snapshot(worker_timeout_threshold=2700, max_stale_task_minutes=30),
        "WORKER_TIMEOUT_THRESHOLD < MAX_STALE_TASK_MINUTES * 60",
    )


def test_watchdog_exactly_at_worker_guard_violates():
    _assert_violates(
        _snapshot(worker_timeout_threshold=3600, max_stale_task_minutes=60),
        "WORKER_TIMEOUT_THRESHOLD < MAX_STALE_TASK_MINUTES * 60",
    )


def test_watchdog_disabled_by_zero_is_not_a_violation():
    violations = check_threshold_invariants(_snapshot(max_stale_task_minutes=0))
    assert violations == []


# ---------------------------------------------------------------------------
# Invariant 3 — PR_CHECKS_EMPTY_GRACE_S * 2 < PR_CHECKS_TIMEOUT_S
# ---------------------------------------------------------------------------

def test_grace_exceeding_half_the_poll_budget_violates():
    _assert_violates(
        _snapshot(pr_checks_empty_grace_s=700, pr_checks_timeout_s=1200),
        "PR_CHECKS_EMPTY_GRACE_S * 2 < PR_CHECKS_TIMEOUT_S",
    )


def test_grace_exactly_half_the_poll_budget_violates():
    """Exactly two grace windows leaves no time to act on the second one."""
    _assert_violates(
        _snapshot(pr_checks_empty_grace_s=600, pr_checks_timeout_s=1200),
        "PR_CHECKS_EMPTY_GRACE_S * 2 < PR_CHECKS_TIMEOUT_S",
    )


def test_grace_just_under_half_is_healthy():
    assert check_threshold_invariants(
        _snapshot(pr_checks_empty_grace_s=599, pr_checks_timeout_s=1200)
    ) == []


# ---------------------------------------------------------------------------
# Invariant 4 — STALE_RUN_WARN_MINUTES < MAX_STALE_TASK_MINUTES
# ---------------------------------------------------------------------------

def test_warn_at_or_after_hard_stop_violates():
    _assert_violates(
        _snapshot(stale_run_warn_minutes=120, max_stale_task_minutes=120),
        "STALE_RUN_WARN_MINUTES < MAX_STALE_TASK_MINUTES",
    )


def test_warn_disabled_by_zero_is_not_a_violation():
    violations = check_threshold_invariants(_snapshot(stale_run_warn_minutes=0))
    assert "STALE_RUN_WARN_MINUTES < MAX_STALE_TASK_MINUTES" not in _invariants(violations)


# ---------------------------------------------------------------------------
# Invariant 5 — MAX_STALE_TASK_MINUTES < MAX_RUNTIME_MINUTES
# ---------------------------------------------------------------------------

def test_runtime_budget_below_watchdog_violates():
    _assert_violates(
        _snapshot(max_stale_task_minutes=120, max_runtime_minutes=90),
        "MAX_STALE_TASK_MINUTES < MAX_RUNTIME_MINUTES",
    )


# ---------------------------------------------------------------------------
# Invariant 6 — retry backoff budget fits inside the stale window
# ---------------------------------------------------------------------------

def test_backoff_budget_overrunning_stale_window_violates():
    _assert_violates(
        _snapshot(
            worker_timeout_threshold=2700,
            failure_retry_backoff_max_s=3000.0,
            max_task_attempts=3,
            max_stale_task_minutes=120,
        ),
        "FAILURE_RETRY_BACKOFF_MAX_S",
    )


def test_single_attempt_has_no_backoff_budget():
    """With one attempt there is no retry, so no backoff to budget for."""
    violations = check_threshold_invariants(_snapshot(
        failure_retry_backoff_max_s=99999.0, max_task_attempts=1,
    ))
    assert not [v for v in violations if "FAILURE_RETRY_BACKOFF_MAX_S" in v["invariant"]]


# ---------------------------------------------------------------------------
# Violation payload and formatting
# ---------------------------------------------------------------------------

def test_every_violation_carries_message_fix_and_values():
    violations = check_threshold_invariants(_snapshot(
        claude_cli_timeout_s=1800,
        worker_timeout_threshold=570,
        max_stale_task_minutes=5,
    ))
    assert len(violations) >= 2
    for v in violations:
        assert v["invariant"] and v["message"] and v["fix"]
        assert isinstance(v["values"], dict) and v["values"]


def test_format_violations_names_each_rule_and_fix():
    violations = check_threshold_invariants(
        _snapshot(claude_cli_timeout_s=2400, worker_timeout_threshold=570)
    )
    text = format_violations(violations)
    assert "CLAUDE_CLI_TIMEOUT_S < WORKER_TIMEOUT_THRESHOLD" in text
    assert "Fix:" in text
    assert "M4C0-THRESHOLD-CALIBRATION.md" in text


def test_format_violations_empty_when_healthy():
    assert format_violations([]) == ""


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_healthy_snapshot_has_no_violations,
        test_shipped_defaults_satisfy_every_invariant,
        test_shipped_profiles_satisfy_every_invariant,
        test_empty_snapshot_is_not_a_violation,
        test_non_numeric_values_are_skipped,
        test_cli_timeout_above_guard_violates,
        test_pre_m4c0_defaults_are_caught,
        test_cli_timeout_equal_to_guard_violates,
        test_guard_disabled_by_zero_is_not_a_violation,
        test_watchdog_below_worker_guard_violates,
        test_watchdog_exactly_at_worker_guard_violates,
        test_watchdog_disabled_by_zero_is_not_a_violation,
        test_grace_exceeding_half_the_poll_budget_violates,
        test_grace_exactly_half_the_poll_budget_violates,
        test_grace_just_under_half_is_healthy,
        test_warn_at_or_after_hard_stop_violates,
        test_warn_disabled_by_zero_is_not_a_violation,
        test_runtime_budget_below_watchdog_violates,
        test_backoff_budget_overrunning_stale_window_violates,
        test_single_attempt_has_no_backoff_budget,
        test_every_violation_carries_message_fix_and_values,
        test_format_violations_names_each_rule_and_fix,
        test_format_violations_empty_when_healthy,
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
