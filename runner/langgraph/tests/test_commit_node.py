"""Unit tests for commit handling — regression for deploy being skipped when the
worker committed its own changes.

Runs standalone (no pytest dependency), mirroring test_deploy_node.py:

    python tests/test_commit_node.py

Workers are asked to commit their own work (see the task prompt template), so the
runner's own ``git commit`` often finds a clean tree and exits non-zero with
"nothing to commit". That must still count as a landed commit, otherwise
``state.last_commit`` stays None and ``deploy_if_needed`` skips with
"no committed changes to deploy" even though AUTO_DEPLOY is on.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("VERCEL_TOKEN", "test-token")

import graph
from state import RunnerState
import tools.git_tools as git_tools

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None
git_tools.log_event = lambda *a, **k: None


class _FakeGit:
    """Stub for tools.git_tools._git driven by a queue of (success, output)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def __call__(self, args, cwd, timeout=60):
        self.calls.append(args)
        success, output = self._responses.pop(0)
        return type("R", (), {"success": success, "output": output})()


# ---------------------------------------------------------------------------
# commit_all
# ---------------------------------------------------------------------------

def test_commit_all_reports_real_commit():
    # add -A, commit (ok), log --oneline -1
    git_tools._git = _FakeGit([
        (True, ""),
        (True, "[feature abc] msg"),
        (True, "abc1234 msg"),
    ])
    out = git_tools.commit_all("/repo", "msg")
    assert out["success"] is True, out
    assert out["committed"] is True, out
    assert out["nothing_to_commit"] is False, out
    assert out["sha"] == "abc1234 msg", out


def test_commit_all_treats_clean_tree_as_committed():
    # Worker already committed: add -A then commit fails "nothing to commit".
    git_tools._git = _FakeGit([
        (True, ""),
        (False, "On branch feature\nnothing to commit, working tree clean"),
        (True, "wrk5678 worker commit"),
    ])
    out = git_tools.commit_all("/repo", "msg")
    assert out["success"] is False, out
    assert out["committed"] is True, "clean tree must still count as a landed commit"
    assert out["nothing_to_commit"] is True, out
    assert out["sha"] == "wrk5678 worker commit", out


def test_commit_all_real_failure_is_not_committed():
    # A genuine commit error (e.g. hook rejected) must NOT be treated as landed.
    git_tools._git = _FakeGit([
        (True, ""),
        (False, "error: failed to commit, pre-commit hook rejected"),
    ])
    out = git_tools.commit_all("/repo", "msg")
    assert out["success"] is False, out
    assert out["committed"] is False, out
    assert out["nothing_to_commit"] is False, out
    assert out["sha"] == "", out


# ---------------------------------------------------------------------------
# commit_push_merge_if_needed node
# ---------------------------------------------------------------------------

def _worker_done_state():
    return RunnerState(
        current_task_id="t1",
        current_task={"id": "t1", "title": "demo", "branch": "feature/t1"},
        worker_result={"success": True},
        check_passed=True,
    )


def _wire_git(commit_result):
    """Stub the git_tools symbols imported into graph; record push/merge calls."""
    calls = {"push": [], "merge": [], "cleanup": [], "fetch": 0}
    graph.create_branch = lambda repo, branch: {"success": True, "output": ""}
    graph.commit_all = lambda repo, message: commit_result
    graph.push_branch = lambda repo, branch: calls["push"].append(branch)
    def _merge(repo, branch):
        calls["merge"].append(branch)
        return {"success": True, "output": ""}
    graph.merge_feature_branch = _merge
    graph.cleanup_feature_branch = lambda repo, branch: calls["cleanup"].append(branch)
    def _fetch(repo):
        calls["fetch"] += 1
    graph.fetch_pull_main = _fetch
    return calls


def test_node_sets_last_commit_when_worker_already_committed():
    calls = _wire_git({
        "success": False, "committed": True, "nothing_to_commit": True,
        "sha": "wrk5678 worker commit", "output": "nothing to commit",
    })
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert state.last_commit == "wrk5678 worker commit", state.last_commit
    assert calls["push"] == ["feature/t1"], "worker commit should still be pushed"
    assert calls["merge"] == ["feature/t1"], "worker commit should still be merged"
    assert calls["cleanup"] == ["feature/t1"], "merged feature branch should be cleaned up"


def test_node_skips_on_real_commit_failure():
    calls = _wire_git({
        "success": False, "committed": False, "nothing_to_commit": False,
        "sha": "", "output": "hook rejected",
    })
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert state.last_commit is None, state.last_commit
    assert calls["push"] == [], "nothing should be pushed on a real commit failure"
    assert calls["merge"] == [], calls
    assert calls["cleanup"] == [], calls


def test_node_sets_last_commit_on_normal_commit():
    calls = _wire_git({
        "success": True, "committed": True, "nothing_to_commit": False,
        "sha": "abc1234 msg", "output": "",
    })
    graph.cfg.auto_merge = False
    graph.cfg.auto_cleanup_branches = True

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert state.last_commit == "abc1234 msg", state.last_commit
    assert calls["push"] == ["feature/t1"], calls
    assert calls["merge"] == [], "no merge when auto_merge is off"
    assert calls["cleanup"] == [], "no cleanup when auto_merge is off"


def test_node_skips_cleanup_when_merge_fails():
    calls = _wire_git({
        "success": True, "committed": True, "nothing_to_commit": False,
        "sha": "abc1234 msg", "output": "",
    })
    graph.merge_feature_branch = lambda repo, branch: (
        calls["merge"].append(branch) or {"success": False, "output": "conflict"}
    )
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = True

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert state.last_commit == "abc1234 msg", state.last_commit
    assert calls["push"] == ["feature/t1"], calls
    assert calls["merge"] == ["feature/t1"], calls
    assert calls["fetch"] == 0, "must not fetch main after a failed merge"
    assert calls["cleanup"] == [], "must not clean up branch after a failed merge"


def test_node_respects_branch_cleanup_flag():
    calls = _wire_git({
        "success": True, "committed": True, "nothing_to_commit": False,
        "sha": "abc1234 msg", "output": "",
    })
    graph.cfg.auto_merge = True
    graph.cfg.auto_cleanup_branches = False

    state = graph.commit_push_merge_if_needed(_worker_done_state())

    assert state.last_commit == "abc1234 msg", state.last_commit
    assert calls["push"] == ["feature/t1"], calls
    assert calls["merge"] == ["feature/t1"], calls
    assert calls["fetch"] == 1, calls
    assert calls["cleanup"] == [], "cleanup disabled by config"


if __name__ == "__main__":
    tests = [
        test_commit_all_reports_real_commit,
        test_commit_all_treats_clean_tree_as_committed,
        test_commit_all_real_failure_is_not_committed,
        test_node_sets_last_commit_when_worker_already_committed,
        test_node_skips_on_real_commit_failure,
        test_node_sets_last_commit_on_normal_commit,
        test_node_skips_cleanup_when_merge_fails,
        test_node_respects_branch_cleanup_flag,
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
