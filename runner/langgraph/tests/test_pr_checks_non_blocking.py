"""Advisory (non-blocking) check runs must never fail a PR merge.

Regression origin — 2026-08-02, M4c pre-patch. Task m4c-01 exhausted its
retries with `pr_checks_failed: PR #94 required checks did not pass` while the
actual conclusions were:

    Lint, typecheck, build                            success
    Runner tests                                      success
    E2E (Playwright)                                  success
    Vercel Preview Comments                           success
    E2E (Playwright, Vercel preview) [informational]  failure   <-- only failure

The last job is informational BY DESIGN (built that way in M2 — the preview
deployment is flaky/absent for many PRs). `poll_pr_checks` required every run
to be success/skipped, making the runner stricter than the repo's own branch
protection and stranding correct work. The loop then died on `stale_run`.

These tests pin: advisory failures are reported but not fatal; genuinely
required failures still fail; matching is case-insensitive and substring-based;
and an empty allowlist restores strict behavior.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import tools.github_tools as github_tools

from test_pr_merge_flow import (  # reuse the existing harness
    FakeClock,
    _FakeConfig,
    _FakeResponse,
    _queue_get,
    _with_fake_config,
)

# The exact conclusions observed on PR #94.
PR_94_RUNS = [
    {"name": "Vercel Preview Comments", "status": "completed", "conclusion": "success"},
    {"name": "E2E (Playwright)", "status": "completed", "conclusion": "success"},
    {"name": "Lint, typecheck, build", "status": "completed", "conclusion": "success"},
    {"name": "E2E (Playwright, Vercel preview) [informational]",
     "status": "completed", "conclusion": "failure"},
    {"name": "Runner tests", "status": "completed", "conclusion": "success"},
]


def _poll(runs, cfg=None):
    clock = FakeClock()
    github_tools.requests.get = _queue_get([
        _FakeResponse(200, json_data={"check_runs": runs}),
    ])
    return _with_fake_config(
        cfg or _FakeConfig(),
        lambda: github_tools.poll_pr_checks(
            "owner/repo", "abc123", timeout_s=100, interval_s=1,
            sleep=clock.sleep, now=clock.now,
        ),
    )


def test_pr_94_scenario_now_succeeds():
    result = _poll(PR_94_RUNS)
    assert result["success"] is True, result
    assert result["timed_out"] is False, result


def test_required_failure_still_fails_even_with_advisory_present():
    runs = [dict(r) for r in PR_94_RUNS]
    for r in runs:
        if r["name"] == "Runner tests":
            r["conclusion"] = "failure"
    result = _poll(runs)
    assert result["success"] is False, result
    assert result["timed_out"] is False, result


def test_advisory_matching_is_case_insensitive():
    runs = [
        {"name": "Build", "status": "completed", "conclusion": "success"},
        {"name": "Preview E2E [INFORMATIONAL]", "status": "completed", "conclusion": "failure"},
    ]
    assert _poll(runs)["success"] is True


def test_empty_allowlist_restores_strict_behavior():
    result = _poll(PR_94_RUNS, cfg=_FakeConfig(non_blocking=[]))
    assert result["success"] is False, result


def test_custom_allowlist_substring():
    runs = [
        {"name": "Runner tests", "status": "completed", "conclusion": "success"},
        {"name": "flaky-smoke", "status": "completed", "conclusion": "failure"},
    ]
    assert _poll(runs, cfg=_FakeConfig(non_blocking=["flaky"]))["success"] is True
    assert _poll(runs, cfg=_FakeConfig(non_blocking=["other"]))["success"] is False


def test_advisory_success_is_not_special_cased():
    # An advisory job that PASSES must not change the outcome either way.
    runs = [
        {"name": "Runner tests", "status": "completed", "conclusion": "success"},
        {"name": "preview [informational]", "status": "completed", "conclusion": "success"},
    ]
    assert _poll(runs)["success"] is True


def test_all_advisory_and_all_failing_still_merges():
    # Degenerate but defined: if literally every run is advisory, nothing gates.
    runs = [
        {"name": "a [informational]", "status": "completed", "conclusion": "failure"},
        {"name": "b [informational]", "status": "completed", "conclusion": "failure"},
    ]
    assert _poll(runs)["success"] is True


def test_config_default_and_env_override(monkeypatch):
    import config as config_module

    monkeypatch.delenv("PR_CHECKS_NON_BLOCKING", raising=False)
    assert config_module.RunnerConfig().pr_checks_non_blocking == ["[informational]"]

    monkeypatch.setenv("PR_CHECKS_NON_BLOCKING", "[informational], Flaky ,")
    assert config_module.RunnerConfig().pr_checks_non_blocking == ["[informational]", "flaky"]
