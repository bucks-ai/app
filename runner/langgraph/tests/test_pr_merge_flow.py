"""Unit tests for the PR-based merge flow (M0.8b).

Covers three layers:
  1. tools.github_tools REST helpers (create_pull_request, poll_pr_checks,
     merge_pull_request) — requests.get/post/put are stubbed, no network.
  2. graph._merge_via_pull_request / commit_push_merge_if_needed — the three
     REST helpers are stubbed at the graph level (same pattern as
     test_commit_node.py), no network and no real git.
  3. config wiring — MERGE_VIA_PR / PR_CHECKS_TIMEOUT_S / PR_CHECKS_POLL_INTERVAL_S
     defaults, report() keys, and the two new curated Slack events.

Runs standalone (no pytest dependency), mirroring test_commit_node.py:

    python tests/test_pr_merge_flow.py
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("VERCEL_TOKEN", "test-token")

import requests

import graph
import config as config_module
import tools.github_tools as github_tools
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None
github_tools.log_event = lambda *a, **k: None


class FakeClock:
    """Monotonic clock that only advances when sleep() is called."""

    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = {} if json_data is None else json_data
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.exceptions.HTTPError(f"{self.status_code} Client Error")
            err.response = self
            raise err

    def json(self):
        return self._json_data


class _FakeConfig:
    """Minimal stand-in for RunnerConfig, used to isolate github_tools tests
    from the real process-wide config singleton."""

    def __init__(self, github_token="test-token", timeout=900, interval=20, empty_grace=180):
        self.github_token = github_token
        self.pr_checks_timeout_s = timeout
        self.pr_checks_poll_interval_s = interval
        self.pr_checks_empty_grace_s = empty_grace

    @property
    def has_github(self):
        return bool(self.github_token)


def _with_fake_config(cfg, fn):
    original = github_tools.get_config
    github_tools.get_config = lambda: cfg
    try:
        return fn()
    finally:
        github_tools.get_config = original


def _queue_get(responses):
    responses = list(responses)

    def _get(*args, **kwargs):
        return responses.pop(0)

    return _get


# ---------------------------------------------------------------------------
# create_pull_request
# ---------------------------------------------------------------------------

def test_create_pull_request_creates_new_pr():
    calls = {"get": 0, "post": 0}

    def _get(url, headers=None, params=None, timeout=None):
        calls["get"] += 1
        assert params["head"] == "owner:feature/t1", params
        return _FakeResponse(200, json_data=[])

    def _post(url, headers=None, json=None, timeout=None):
        calls["post"] += 1
        assert json["head"] == "feature/t1", json
        return _FakeResponse(201, json_data={"number": 42, "html_url": "https://github.test/owner/repo/pull/42"})

    github_tools.requests.get = _get
    github_tools.requests.post = _post

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.create_pull_request("owner/repo", "feature/t1", "Task title", "body text"),
    )

    assert result["success"] is True, result
    assert result["created"] is True, result
    assert result["number"] == 42, result
    assert result["url"] == "https://github.test/owner/repo/pull/42", result
    assert calls == {"get": 1, "post": 1}, calls


def test_create_pull_request_is_idempotent_when_pr_exists():
    calls = {"get": 0, "post": 0}

    def _get(url, headers=None, params=None, timeout=None):
        calls["get"] += 1
        return _FakeResponse(200, json_data=[{"number": 7, "html_url": "https://github.test/owner/repo/pull/7"}])

    def _post(*a, **k):
        calls["post"] += 1
        raise AssertionError("should not create a duplicate PR")

    github_tools.requests.get = _get
    github_tools.requests.post = _post

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.create_pull_request("owner/repo", "feature/t1", "Task title", "body text"),
    )

    assert result["success"] is True, result
    assert result["created"] is False, result
    assert result["number"] == 7, result
    assert calls == {"get": 1, "post": 0}, calls


def test_create_pull_request_degrades_without_token():
    result = _with_fake_config(
        _FakeConfig(github_token=None),
        lambda: github_tools.create_pull_request("owner/repo", "feature/t1", "Task title", "body text"),
    )
    assert result == {"success": False, "reason": "no GITHUB_TOKEN"}, result


def test_create_pull_request_no_diff_treated_as_success():
    """GitHub returns 422 'No commits between <base> and <branch>' when the
    feature branch has no commits ahead of base (worker made no net changes).
    That is not a real PR-creation failure — there is nothing to merge — so it
    must surface as a distinct no_diff success, not success=False."""
    def _get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(200, json_data=[])

    def _post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(
            422,
            text='{"message":"Validation Failed","errors":[{"resource":"PullRequest",'
                 '"code":"custom","message":"No commits between main and feature/t1"}]}',
        )

    github_tools.requests.get = _get
    github_tools.requests.post = _post

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.create_pull_request("owner/repo", "feature/t1", "Task title", "body text"),
    )

    assert result["success"] is True, result
    assert result["created"] is False, result
    assert result["no_diff"] is True, result
    assert result["number"] is None, result


def test_create_pull_request_other_422_still_fails():
    """A 422 for a different reason (e.g. invalid field) must still be a real
    failure — only the specific 'no commits between' message is a no-op."""
    def _get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(200, json_data=[])

    def _post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(422, text='{"message":"Validation Failed","errors":[{"code":"invalid"}]}')

    github_tools.requests.get = _get
    github_tools.requests.post = _post

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.create_pull_request("owner/repo", "feature/t1", "Task title", "body text"),
    )

    assert result["success"] is False, result
    assert result.get("no_diff") is not True, result


# ---------------------------------------------------------------------------
# poll_pr_checks
# ---------------------------------------------------------------------------

def test_poll_pr_checks_succeeds_when_all_conclusions_pass():
    clock = FakeClock()
    github_tools.requests.get = _queue_get([
        _FakeResponse(200, json_data={"check_runs": [{"name": "build", "status": "in_progress"}]}),
        _FakeResponse(200, json_data={"check_runs": [
            {"name": "build", "status": "completed", "conclusion": "success"},
            {"name": "lint", "status": "completed", "conclusion": "skipped"},
        ]}),
    ])

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.poll_pr_checks(
            "owner/repo", "abc123", timeout_s=100, interval_s=1, sleep=clock.sleep, now=clock.now,
        ),
    )

    assert result["success"] is True, result
    assert result["timed_out"] is False, result
    assert result["polls"] == 2, result


def test_poll_pr_checks_fails_on_a_failed_conclusion():
    clock = FakeClock()
    github_tools.requests.get = _queue_get([
        _FakeResponse(200, json_data={"check_runs": [
            {"name": "build", "status": "completed", "conclusion": "success"},
            {"name": "runner-tests", "status": "completed", "conclusion": "failure"},
        ]}),
    ])

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.poll_pr_checks(
            "owner/repo", "abc123", timeout_s=100, interval_s=1, sleep=clock.sleep, now=clock.now,
        ),
    )

    assert result["success"] is False, result
    assert result["timed_out"] is False, result
    assert result["polls"] == 1, result


def test_poll_pr_checks_times_out_when_never_complete():
    clock = FakeClock()
    github_tools.requests.get = lambda *a, **k: _FakeResponse(
        200, json_data={"check_runs": [{"name": "build", "status": "in_progress"}]}
    )

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.poll_pr_checks(
            "owner/repo", "abc123", timeout_s=3, interval_s=1, sleep=clock.sleep, now=clock.now,
        ),
    )

    assert result["success"] is False, result
    assert result["timed_out"] is True, result
    assert result["polls"] == 3, result


def test_poll_pr_checks_treats_empty_runs_as_not_complete():
    clock = FakeClock()
    github_tools.requests.get = _queue_get([
        _FakeResponse(200, json_data={"check_runs": []}),
        _FakeResponse(200, json_data={"check_runs": [{"name": "build", "status": "completed", "conclusion": "success"}]}),
    ])

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.poll_pr_checks(
            "owner/repo", "abc123", timeout_s=100, interval_s=1, sleep=clock.sleep, now=clock.now,
        ),
    )

    assert result["success"] is True, result
    assert result["polls"] == 2, result


def _routed_get(check_runs_responses, pr_details_response=None):
    """Fake requests.get that routes on URL: .../check-runs vs .../pulls/{n}."""
    check_runs_responses = list(check_runs_responses)

    def _get(url, headers=None, params=None, timeout=None):
        if url.endswith("/check-runs"):
            return check_runs_responses.pop(0)
        return pr_details_response

    return _get


def test_poll_pr_checks_empty_runs_recovers_via_branch_update_when_conflicting():
    """Live-incident scenario: check_runs stays empty past the grace window.
    Mergeable state is 'dirty' (conflicting), so the branch should be
    refreshed exactly once via update-branch, and polling should continue
    (not fail) once real check runs eventually show up."""
    clock = FakeClock()
    github_tools.requests.get = _routed_get(
        [
            _FakeResponse(200, json_data={"check_runs": []}),   # elapsed 0
            _FakeResponse(200, json_data={"check_runs": []}),   # elapsed 10 -> hits grace(10)
            _FakeResponse(200, json_data={"check_runs": [
                {"name": "build", "status": "completed", "conclusion": "success"},
            ]}),
        ],
        pr_details_response=_FakeResponse(200, json_data={"mergeable_state": "dirty"}),
    )
    put_calls = []

    def _put(url, headers=None, timeout=None):
        put_calls.append(url)
        return _FakeResponse(202, json_data={})

    github_tools.requests.put = _put

    result = _with_fake_config(
        _FakeConfig(empty_grace=10),
        lambda: github_tools.poll_pr_checks(
            "owner/repo", "abc123", timeout_s=100, interval_s=10,
            sleep=clock.sleep, now=clock.now, pr_number=42,
        ),
    )

    assert result["success"] is True, result
    assert result["polls"] == 3, result
    assert put_calls == ["https://api.github.com/repos/owner/repo/pulls/42/update-branch"], put_calls


def test_poll_pr_checks_empty_runs_skips_update_when_mergeable_clean():
    """If the PR is already clean/unblocked, empty check runs are just a slow
    webhook — don't call update-branch, just keep polling."""
    clock = FakeClock()
    github_tools.requests.get = _routed_get(
        [
            _FakeResponse(200, json_data={"check_runs": []}),
            _FakeResponse(200, json_data={"check_runs": []}),
            _FakeResponse(200, json_data={"check_runs": [
                {"name": "build", "status": "completed", "conclusion": "success"},
            ]}),
        ],
        pr_details_response=_FakeResponse(200, json_data={"mergeable_state": "clean"}),
    )

    def _put(*a, **k):
        raise AssertionError("must not update branch when mergeable_state is clean")

    github_tools.requests.put = _put

    result = _with_fake_config(
        _FakeConfig(empty_grace=10),
        lambda: github_tools.poll_pr_checks(
            "owner/repo", "abc123", timeout_s=100, interval_s=10,
            sleep=clock.sleep, now=clock.now, pr_number=42,
        ),
    )

    assert result["success"] is True, result


def test_poll_pr_checks_fails_fast_with_no_runs_after_second_grace_window():
    """Zero check runs ever scheduled (e.g. a dropped Actions webhook) must
    fail fast with the distinct reason 'pr_checks_no_runs' — never the
    generic timeout — once a second grace window elapses with still no runs."""
    clock = FakeClock()
    github_tools.requests.get = _routed_get(
        [_FakeResponse(200, json_data={"check_runs": []}) for _ in range(10)],
        pr_details_response=_FakeResponse(200, json_data={"mergeable_state": "clean"}),
    )
    github_tools.requests.put = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("must not update branch when mergeable_state is clean")
    )

    result = _with_fake_config(
        _FakeConfig(empty_grace=10),
        lambda: github_tools.poll_pr_checks(
            "owner/repo", "abc123", timeout_s=900, interval_s=10,
            sleep=clock.sleep, now=clock.now, pr_number=42,
        ),
    )

    assert result["success"] is False, result
    assert result["timed_out"] is False, "must be distinct from a generic timeout"
    assert result["reason"] == "pr_checks_no_runs", result


def test_poll_pr_checks_no_runs_fail_fast_works_without_pr_number():
    """Callers that don't pass pr_number (can't query mergeable state/update
    the branch) must still fail fast with pr_checks_no_runs after the second
    grace window, rather than hanging until the generic timeout."""
    clock = FakeClock()
    github_tools.requests.get = lambda *a, **k: _FakeResponse(200, json_data={"check_runs": []})

    result = _with_fake_config(
        _FakeConfig(empty_grace=10),
        lambda: github_tools.poll_pr_checks(
            "owner/repo", "abc123", timeout_s=900, interval_s=10,
            sleep=clock.sleep, now=clock.now,
        ),
    )

    assert result["success"] is False, result
    assert result["reason"] == "pr_checks_no_runs", result


# ---------------------------------------------------------------------------
# merge_pull_request
# ---------------------------------------------------------------------------

def test_merge_pull_request_success():
    github_tools.requests.put = lambda url, headers=None, json=None, timeout=None: _FakeResponse(
        200, json_data={"merged": True, "sha": "def456", "message": "Pull Request successfully merged"}
    )

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.merge_pull_request("owner/repo", 42),
    )

    assert result["success"] is True, result
    assert result["sha"] == "def456", result


def test_merge_pull_request_surfaces_405_rejection():
    github_tools.requests.put = lambda url, headers=None, json=None, timeout=None: _FakeResponse(
        405, text='{"message": "Pull Request is not mergeable"}'
    )

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.merge_pull_request("owner/repo", 42),
    )

    assert result["success"] is False, result
    assert result["status_code"] == 405, result
    assert "not mergeable" in result["error_body"], result


def test_merge_pull_request_surfaces_409_conflict():
    github_tools.requests.put = lambda url, headers=None, json=None, timeout=None: _FakeResponse(
        409, text='{"message": "Head branch was modified"}'
    )

    result = _with_fake_config(
        _FakeConfig(),
        lambda: github_tools.merge_pull_request("owner/repo", 42),
    )

    assert result["success"] is False, result
    assert result["status_code"] == 409, result
    assert "modified" in result["error_body"], result


# ---------------------------------------------------------------------------
# graph.commit_push_merge_if_needed — PR-based merge path (MERGE_VIA_PR=true)
# ---------------------------------------------------------------------------

def _worker_done_state():
    return RunnerState(
        current_task_id="t1",
        current_task={"id": "t1", "title": "demo", "branch": "feature/t1"},
        worker_result={"success": True},
        check_passed=True,
    )


def _wire_for_pr_merge(commit_result, *, create_result, checks_result, merge_result):
    calls = {"push": [], "create_pr": [], "poll_checks": [], "merge_pr": [], "cleanup": [], "fetch": 0}
    graph.create_branch = lambda repo, branch: {"success": True, "output": ""}
    graph.commit_all = lambda repo, message: commit_result
    graph.push_branch = lambda repo, branch: calls["push"].append(branch)
    graph.current_commit_sha = lambda repo: "deadbeef"

    def _create_pr(repo, branch, title, body):
        calls["create_pr"].append((repo, branch))
        return create_result
    graph.create_pull_request = _create_pr

    def _poll_checks(repo, sha, timeout_s=None, interval_s=None, pr_number=None):
        calls["poll_checks"].append((repo, sha))
        return checks_result
    graph.poll_pr_checks = _poll_checks

    def _merge_pr(repo, number):
        calls["merge_pr"].append((repo, number))
        return merge_result
    graph.merge_pull_request = _merge_pr

    def _fetch(repo):
        calls["fetch"] += 1
    graph.fetch_pull_main = _fetch
    graph.cleanup_feature_branch = lambda repo, branch, **kw: calls["cleanup"].append(branch)
    return calls


_LANDED_COMMIT = {"success": True, "committed": True, "nothing_to_commit": False, "sha": "abc1234 msg", "output": ""}


def test_pr_merge_happy_path_merges_and_cleans_up():
    calls = _wire_for_pr_merge(
        _LANDED_COMMIT,
        create_result={"success": True, "created": True, "number": 42, "url": "https://github.test/pull/42"},
        checks_result={"success": True, "timed_out": False},
        merge_result={"success": True, "sha": "def456"},
    )
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True
    graph.cfg.merge_via_pr = True
    graph.cfg.github_token = "test-token"
    graph.cfg.github_repo = "owner/repo"

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert calls["create_pr"] == [("owner/repo", "feature/t1")], calls
    assert calls["poll_checks"] == [("owner/repo", "deadbeef")], calls
    assert calls["merge_pr"] == [("owner/repo", 42)], calls
    assert calls["fetch"] == 1, calls
    assert calls["cleanup"] == ["feature/t1"], calls
    assert state.pr_number == 42, state
    assert state.pr_url == "https://github.test/pull/42", state
    assert state.worker_result["success"] is True, state.worker_result


def test_pr_merge_checks_failure_marks_task_failed_and_leaves_pr_open():
    calls = _wire_for_pr_merge(
        _LANDED_COMMIT,
        create_result={"success": True, "created": True, "number": 42, "url": "https://github.test/pull/42"},
        checks_result={"success": False, "timed_out": False},
        merge_result={"success": True, "sha": "def456"},
    )
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True
    graph.cfg.merge_via_pr = True
    graph.cfg.github_token = "test-token"
    graph.cfg.github_repo = "owner/repo"

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert calls["merge_pr"] == [], "must not merge when checks failed"
    assert calls["fetch"] == 0, "must not fast-forward main when checks failed"
    assert calls["cleanup"] == [], "PR must be left open, branch not cleaned up"
    assert state.worker_result["success"] is False, state.worker_result
    assert "pr_checks_failed" in state.worker_result["error"], state.worker_result


def test_pr_merge_checks_timeout_marks_task_failed_distinctly():
    calls = _wire_for_pr_merge(
        _LANDED_COMMIT,
        create_result={"success": True, "created": True, "number": 42, "url": "https://github.test/pull/42"},
        checks_result={"success": False, "timed_out": True},
        merge_result={"success": True, "sha": "def456"},
    )
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True
    graph.cfg.merge_via_pr = True
    graph.cfg.github_token = "test-token"
    graph.cfg.github_repo = "owner/repo"

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert calls["merge_pr"] == [], calls
    assert state.worker_result["success"] is False, state.worker_result
    assert "pr_checks_timeout" in state.worker_result["error"], state.worker_result


def test_pr_merge_checks_no_runs_marks_task_failed_distinctly():
    """A PR that never had any check runs scheduled (poll_pr_checks returned
    reason='pr_checks_no_runs') must be marked failed with that distinct
    reason — never generic pr_checks_failed/pr_checks_timeout text — and
    must not merge, matching the timeout/failed cases above."""
    calls = _wire_for_pr_merge(
        _LANDED_COMMIT,
        create_result={"success": True, "created": True, "number": 42, "url": "https://github.test/pull/42"},
        checks_result={"success": False, "timed_out": False, "reason": "pr_checks_no_runs"},
        merge_result={"success": True, "sha": "def456"},
    )
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True
    graph.cfg.merge_via_pr = True
    graph.cfg.github_token = "test-token"
    graph.cfg.github_repo = "owner/repo"

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert calls["merge_pr"] == [], "must not merge when no check runs were ever scheduled"
    assert calls["fetch"] == 0, calls
    assert calls["cleanup"] == [], "PR must be left open, branch not cleaned up"
    assert state.worker_result["success"] is False, state.worker_result
    assert "pr_checks_no_runs" in state.worker_result["error"], state.worker_result


def test_pr_merge_rejected_by_branch_protection_marks_task_failed():
    calls = _wire_for_pr_merge(
        _LANDED_COMMIT,
        create_result={"success": True, "created": True, "number": 42, "url": "https://github.test/pull/42"},
        checks_result={"success": True, "timed_out": False},
        merge_result={"success": False, "status_code": 405, "error_body": '{"message": "not mergeable"}'},
    )
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True
    graph.cfg.merge_via_pr = True
    graph.cfg.github_token = "test-token"
    graph.cfg.github_repo = "owner/repo"

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert calls["fetch"] == 0, "must not fast-forward main on a rejected merge"
    assert calls["cleanup"] == [], calls
    assert state.worker_result["success"] is False, state.worker_result
    assert "pr_merge_failed" in state.worker_result["error"], state.worker_result
    assert "not mergeable" in state.worker_result["error"], state.worker_result


def test_pr_merge_idempotent_pr_reuse_still_polls_and_merges():
    calls = _wire_for_pr_merge(
        _LANDED_COMMIT,
        create_result={"success": True, "created": False, "number": 99, "url": "https://github.test/pull/99"},
        checks_result={"success": True, "timed_out": False},
        merge_result={"success": True, "sha": "def456"},
    )
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True
    graph.cfg.merge_via_pr = True
    graph.cfg.github_token = "test-token"
    graph.cfg.github_repo = "owner/repo"

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert state.pr_number == 99, state
    assert calls["merge_pr"] == [("owner/repo", 99)], calls


def test_pr_merge_skips_cleanly_without_github_configured():
    calls = _wire_for_pr_merge(
        _LANDED_COMMIT,
        create_result={"success": True, "created": True, "number": 42, "url": "https://github.test/pull/42"},
        checks_result={"success": True, "timed_out": False},
        merge_result={"success": True, "sha": "def456"},
    )
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True
    graph.cfg.merge_via_pr = True
    graph.cfg.github_token = None
    graph.cfg.github_repo = None

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert calls["create_pr"] == [], "no PR should be attempted without GITHUB_TOKEN/GITHUB_REPO"
    assert state.worker_result["success"] is True, state.worker_result


def test_pr_merge_no_diff_treated_as_success_and_cleans_up_branch():
    """When create_pull_request reports no_diff (branch has no commits ahead of
    base), the task must still succeed — checks/merge are skipped since there
    is nothing to merge, and the now-redundant branch is cleaned up."""
    calls = _wire_for_pr_merge(
        _LANDED_COMMIT,
        create_result={"success": True, "created": False, "no_diff": True, "number": None, "url": None},
        checks_result={"success": True, "timed_out": False},
        merge_result={"success": True, "sha": "def456"},
    )
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True
    graph.cfg.merge_via_pr = True
    graph.cfg.github_token = "test-token"
    graph.cfg.github_repo = "owner/repo"

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert calls["create_pr"] == [("owner/repo", "feature/t1")], calls
    assert calls["poll_checks"] == [], "must not poll checks when there is nothing to merge"
    assert calls["merge_pr"] == [], "must not attempt a merge when there is nothing to merge"
    assert calls["fetch"] == 0, calls
    assert calls["cleanup"] == ["feature/t1"], "redundant branch should still be cleaned up"
    assert state.pr_number is None, state
    assert state.worker_result["success"] is True, state.worker_result


# ---------------------------------------------------------------------------
# Config wiring (three-place rule) + curated Slack events
# ---------------------------------------------------------------------------

def test_merge_via_pr_config_defaults():
    # .env may set PR_CHECKS_* for the live runner; isolate this defaults
    # check from it (works standalone, without a pytest monkeypatch fixture).
    keys = ("PR_CHECKS_TIMEOUT_S", "PR_CHECKS_POLL_INTERVAL_S", "PR_CHECKS_EMPTY_GRACE_S")
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        cfg = config_module.RunnerConfig()
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v

    assert cfg.merge_via_pr is True, cfg.merge_via_pr
    assert cfg.pr_checks_timeout_s == 900, cfg.pr_checks_timeout_s
    assert cfg.pr_checks_poll_interval_s == 20, cfg.pr_checks_poll_interval_s
    assert cfg.pr_checks_empty_grace_s == 180, cfg.pr_checks_empty_grace_s
    report = cfg.report()
    assert report["merge_via_pr"] is True, report
    assert report["pr_checks_timeout_s"] == 900, report
    assert report["pr_checks_poll_interval_s"] == 20, report
    assert report["pr_checks_empty_grace_s"] == 180, report


def test_merge_via_pr_config_env_overrides(monkeypatch):
    monkeypatch.setenv("MERGE_VIA_PR", "false")
    monkeypatch.setenv("PR_CHECKS_TIMEOUT_S", "60")
    monkeypatch.setenv("PR_CHECKS_POLL_INTERVAL_S", "5")
    monkeypatch.setenv("PR_CHECKS_EMPTY_GRACE_S", "30")
    cfg = config_module.RunnerConfig()
    assert cfg.merge_via_pr is False, cfg.merge_via_pr
    assert cfg.pr_checks_timeout_s == 60, cfg.pr_checks_timeout_s
    assert cfg.pr_checks_poll_interval_s == 5, cfg.pr_checks_poll_interval_s
    assert cfg.pr_checks_empty_grace_s == 30, cfg.pr_checks_empty_grace_s


def test_pr_checks_events_are_in_curated_slack_set():
    assert "pr_checks_failed" in config_module._DEFAULT_SLACK_EVENTS
    assert "pr_checks_timeout" in config_module._DEFAULT_SLACK_EVENTS
    assert "pr_checks_no_runs" in config_module._DEFAULT_SLACK_EVENTS


if __name__ == "__main__":
    tests = [
        test_create_pull_request_creates_new_pr,
        test_create_pull_request_is_idempotent_when_pr_exists,
        test_create_pull_request_degrades_without_token,
        test_create_pull_request_no_diff_treated_as_success,
        test_create_pull_request_other_422_still_fails,
        test_poll_pr_checks_succeeds_when_all_conclusions_pass,
        test_poll_pr_checks_fails_on_a_failed_conclusion,
        test_poll_pr_checks_times_out_when_never_complete,
        test_poll_pr_checks_treats_empty_runs_as_not_complete,
        test_poll_pr_checks_empty_runs_recovers_via_branch_update_when_conflicting,
        test_poll_pr_checks_empty_runs_skips_update_when_mergeable_clean,
        test_poll_pr_checks_fails_fast_with_no_runs_after_second_grace_window,
        test_poll_pr_checks_no_runs_fail_fast_works_without_pr_number,
        test_merge_pull_request_success,
        test_merge_pull_request_surfaces_405_rejection,
        test_merge_pull_request_surfaces_409_conflict,
        test_pr_merge_happy_path_merges_and_cleans_up,
        test_pr_merge_checks_failure_marks_task_failed_and_leaves_pr_open,
        test_pr_merge_checks_timeout_marks_task_failed_distinctly,
        test_pr_merge_checks_no_runs_marks_task_failed_distinctly,
        test_pr_merge_rejected_by_branch_protection_marks_task_failed,
        test_pr_merge_idempotent_pr_reuse_still_polls_and_merges,
        test_pr_merge_skips_cleanly_without_github_configured,
        test_pr_merge_no_diff_treated_as_success_and_cleans_up_branch,
        test_merge_via_pr_config_defaults,
        test_pr_checks_events_are_in_curated_slack_set,
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
