"""Unit tests for M4b: runner executes missions against a foreign (business) repo.

Runs standalone (no pytest dependency), mirroring test_resource_gate.py:

    python tests/test_foreign_repo_workspace.py

Covers:
  - Pure helpers in tools/foreign_repo_workspace.py: workspace path
    construction (incl. path-traversal safety), the bucks-ai repo guardrail
    (``is_bucks_ai_repo`` / ``guard_business_repo_path``), scoped GitHub
    token resolution (env-by-name, never a stored value), and
    ``ensure_workspace`` (clone-when-new / fetch-when-existing) against a
    fully injected/mocked git runner — no real git binary or network.
  - ``prepare_business_repo`` orchestration: success, no sandbox config,
    forbidden repo, missing secret, workspace error.
  - The graph node ``resolve_business_repo_if_needed``: repo_path override on
    success, hard failure on a forbidden repo / missing business, and the
    resource-gate path for a missing secret (mirrors
    tests/test_resource_gate.py's node-testing style).
  - Routing (``_route_after_business_repo``) and graph wiring.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.foreign_repo_workspace import (
    workspace_dir_for_business,
    is_bucks_ai_repo,
    resolve_scoped_github_token,
    ensure_workspace,
    guard_business_repo_path,
    ForeignRepoGuardError,
    prepare_business_repo,
)
import graph
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


def _cfg(repo_path="/home/arnav/bucks-ai", github_repo="bucks-ai/bucks-ai"):
    return SimpleNamespace(repo_path=repo_path, github_repo=github_repo)


# ---------------------------------------------------------------------------
# workspace_dir_for_business
# ---------------------------------------------------------------------------

def test_workspace_dir_is_under_dot_workspaces():
    path = workspace_dir_for_business("biz-123")
    assert path.endswith(os.path.join(".workspaces", "biz-123")), path
    assert "runner" in path and "langgraph" in path, path


def test_workspace_dir_sanitizes_path_traversal():
    path = workspace_dir_for_business("../../etc/passwd")
    # Separators and dots are stripped — no traversal survives.
    assert ".." not in Path(path).name, path
    assert "etcpasswd" in path.replace(os.sep, ""), path


# ---------------------------------------------------------------------------
# is_bucks_ai_repo — CRITICAL SAFETY guardrail
# ---------------------------------------------------------------------------

def test_is_bucks_ai_repo_matches_configured_repo():
    cfg = _cfg(github_repo="bucks-ai/bucks-ai")
    assert is_bucks_ai_repo("bucks-ai/bucks-ai", cfg) is True
    assert is_bucks_ai_repo("Bucks-AI/Bucks-AI", cfg) is True  # case-insensitive
    assert is_bucks_ai_repo("  bucks-ai/bucks-ai/  ", cfg) is True  # whitespace/slash tolerant


def test_is_bucks_ai_repo_false_for_other_repo():
    cfg = _cfg(github_repo="bucks-ai/bucks-ai")
    assert is_bucks_ai_repo("acme/widgets", cfg) is False


def test_is_bucks_ai_repo_fallback_when_github_repo_unset():
    cfg = _cfg(github_repo=None)
    assert is_bucks_ai_repo("bucks-ai/bucks-ai", cfg) is True
    assert is_bucks_ai_repo("acme/widgets", cfg) is False


def test_is_bucks_ai_repo_empty_input_is_false():
    assert is_bucks_ai_repo("", _cfg()) is False


# ---------------------------------------------------------------------------
# resolve_scoped_github_token
# ---------------------------------------------------------------------------

def test_resolve_scoped_github_token_success():
    os.environ["TEST_M4B_TOKEN_X"] = "ghp_fake_token_value"
    try:
        result = resolve_scoped_github_token("TEST_M4B_TOKEN_X")
        assert result == {"success": True, "token": "ghp_fake_token_value", "secret_name": "TEST_M4B_TOKEN_X"}
    finally:
        del os.environ["TEST_M4B_TOKEN_X"]


def test_resolve_scoped_github_token_missing():
    os.environ.pop("TEST_M4B_TOKEN_MISSING", None)
    result = resolve_scoped_github_token("TEST_M4B_TOKEN_MISSING")
    assert result["success"] is False
    assert result["error"] == "missing_secret"
    assert result["secret_name"] == "TEST_M4B_TOKEN_MISSING"


def test_resolve_scoped_github_token_no_name():
    result = resolve_scoped_github_token("")
    assert result == {"success": False, "error": "no_secret_name"}


# ---------------------------------------------------------------------------
# ensure_workspace — fully mocked git runner, no real network/git binary
# ---------------------------------------------------------------------------

def test_ensure_workspace_clones_when_new():
    calls = []

    def fake_git_run(args, cwd, token, timeout=120):
        calls.append({"args": args, "cwd": cwd, "token": token})
        return {"success": True, "output": "Cloning..."}

    with tempfile.TemporaryDirectory() as d:
        cfg = _cfg(repo_path=str(Path(d) / "bucks-ai"))
        # Point the workspace root somewhere temporary and disposable by
        # monkeypatching the module-level path builder's dependency: we
        # instead just let it build the real .workspaces/ path but redirect
        # via cfg — simplest is to call ensure_workspace directly, which
        # only touches os.makedirs on the parent dir (safe/idempotent) and
        # then hands everything off to fake_git_run (no real clone).
        result = ensure_workspace("biz-abc", "acme/widgets", "shhh-token", cfg, git_run=fake_git_run)

    assert result["success"] is True
    assert result["cloned"] is True
    assert result["fetched"] is False
    assert len(calls) == 1
    clone_call = calls[0]
    assert clone_call["args"][0] == "clone"
    assert "shhh-token" in clone_call["args"][1]
    assert "acme/widgets" in clone_call["args"][1]
    assert clone_call["args"][2].endswith(os.path.join(".workspaces", "biz-abc"))


def test_ensure_workspace_fetches_when_already_cloned():
    calls = []

    def fake_git_run(args, cwd, token, timeout=120):
        calls.append({"args": args, "cwd": cwd})
        return {"success": True, "output": "Fetched."}

    path = workspace_dir_for_business("biz-existing")
    os.makedirs(os.path.join(path, ".git"), exist_ok=True)
    try:
        result = ensure_workspace("biz-existing", "acme/widgets", "shhh-token", _cfg(), git_run=fake_git_run)
    finally:
        import shutil
        shutil.rmtree(path, ignore_errors=True)

    assert result["success"] is True
    assert result["cloned"] is False
    assert result["fetched"] is True
    assert calls[0]["args"] == ["fetch", "origin"]


def test_ensure_workspace_reports_error_on_git_failure():
    def failing_git_run(args, cwd, token, timeout=120):
        return {"success": False, "output": "fatal: repository not found"}

    result = ensure_workspace("biz-fail", "acme/does-not-exist", "shhh-token", _cfg(), git_run=failing_git_run)
    assert result["success"] is False
    assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# guard_business_repo_path — CRITICAL SAFETY: never == bucks-ai repo
# ---------------------------------------------------------------------------

def test_guard_raises_when_repo_path_equals_bucks_ai_repo():
    with tempfile.TemporaryDirectory() as d:
        cfg = _cfg(repo_path=d)
        try:
            guard_business_repo_path(d, cfg)
            assert False, "should have raised ForeignRepoGuardError"
        except ForeignRepoGuardError:
            pass


def test_guard_passes_when_repo_path_differs():
    with tempfile.TemporaryDirectory() as d:
        cfg = _cfg(repo_path=str(Path(d) / "bucks-ai"))
        guard_business_repo_path(str(Path(d) / "workspace"), cfg)  # must not raise


# ---------------------------------------------------------------------------
# prepare_business_repo — orchestration
# ---------------------------------------------------------------------------

def _always_success_git_run(args, cwd, token, timeout=120):
    return {"success": True, "output": "ok"}


def test_prepare_business_repo_success():
    task = {"business_id": "biz-1"}
    business = {
        "id": "biz-1",
        "sandbox_config": {"repo_full_name": "acme/widgets", "github_token_secret_name": "TEST_M4B_TOK"},
    }
    os.environ["TEST_M4B_TOK"] = "shhh-token"
    try:
        with tempfile.TemporaryDirectory() as d:
            cfg = _cfg(repo_path=str(Path(d) / "bucks-ai"))
            result = prepare_business_repo(task, business, cfg, git_run=_always_success_git_run)
    finally:
        del os.environ["TEST_M4B_TOK"]
        import shutil
        shutil.rmtree(workspace_dir_for_business("biz-1"), ignore_errors=True)

    assert result["success"] is True, result
    assert result["repo_full_name"] == "acme/widgets"
    assert result["github_token_secret_name"] == "TEST_M4B_TOK"
    assert result["repo_path"].endswith(os.path.join(".workspaces", "biz-1"))


def test_prepare_business_repo_no_sandbox_config():
    result = prepare_business_repo({"business_id": "biz-2"}, {"id": "biz-2"}, _cfg())
    assert result == {"success": False, "reason": "no_sandbox_config"}


def test_prepare_business_repo_forbidden_repo():
    business = {
        "id": "biz-3",
        "sandbox_config": {"repo_full_name": "bucks-ai/bucks-ai", "github_token_secret_name": "X"},
    }
    result = prepare_business_repo({"business_id": "biz-3"}, business, _cfg(github_repo="bucks-ai/bucks-ai"))
    assert result["success"] is False
    assert result["reason"] == "forbidden_repo"
    assert result["repo_full_name"] == "bucks-ai/bucks-ai"


def test_prepare_business_repo_missing_secret():
    os.environ.pop("TEST_M4B_TOK_MISSING", None)
    business = {
        "id": "biz-4",
        "sandbox_config": {"repo_full_name": "acme/widgets", "github_token_secret_name": "TEST_M4B_TOK_MISSING"},
    }
    result = prepare_business_repo({"business_id": "biz-4"}, business, _cfg())
    assert result == {"success": False, "reason": "missing_secret", "secret_name": "TEST_M4B_TOK_MISSING"}


def test_prepare_business_repo_workspace_error():
    def failing_git_run(args, cwd, token, timeout=120):
        return {"success": False, "output": "fatal: could not resolve host"}

    os.environ["TEST_M4B_TOK_WS"] = "shhh"
    try:
        business = {
            "id": "biz-5",
            "sandbox_config": {"repo_full_name": "acme/widgets", "github_token_secret_name": "TEST_M4B_TOK_WS"},
        }
        result = prepare_business_repo({"business_id": "biz-5"}, business, _cfg(), git_run=failing_git_run)
    finally:
        del os.environ["TEST_M4B_TOK_WS"]
        import shutil
        shutil.rmtree(workspace_dir_for_business("biz-5"), ignore_errors=True)

    assert result["success"] is False
    assert result["reason"] == "workspace_error"


# ---------------------------------------------------------------------------
# Graph node: resolve_business_repo_if_needed
# ---------------------------------------------------------------------------

def _state(task):
    return RunnerState(current_task_id=task.get("id", "t1"), current_task=task)


def _with_temp_runner_dir(fn):
    original = graph._RUNNER_DIR
    failed_calls = []
    blocked_calls = []
    original_failed = graph.mark_task_failed
    original_blocked = graph.mark_task_blocked
    graph.mark_task_failed = lambda task_id, reason: failed_calls.append((task_id, reason))
    graph.mark_task_blocked = lambda task_id, reason: blocked_calls.append((task_id, reason))
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "outbox").mkdir()
        (root / "inbox").mkdir()
        graph._RUNNER_DIR = root
        try:
            return fn(root / "outbox", root / "inbox", failed_calls, blocked_calls)
        finally:
            graph._RUNNER_DIR = original
            graph.mark_task_failed = original_failed
            graph.mark_task_blocked = original_blocked


def test_node_noop_when_no_business_id():
    out = graph.resolve_business_repo_if_needed(_state({"id": "t1"}))
    assert out.stop_reason is None
    assert out.current_task == {"id": "t1"}


def test_node_business_not_found_hard_fails():
    def body(outbox, inbox, failed, blocked):
        original = graph.fetch_business_by_id
        graph.fetch_business_by_id = lambda bid: None
        try:
            out = graph.resolve_business_repo_if_needed(_state({"id": "t1", "business_id": "biz-x"}))
        finally:
            graph.fetch_business_by_id = original
        assert out.stop_reason == "business_not_found"
        assert failed and failed[0][0] == "t1"
    _with_temp_runner_dir(body)


def test_node_success_overrides_repo_path():
    def body(outbox, inbox, failed, blocked):
        original_fetch = graph.fetch_business_by_id
        original_prepare = graph.prepare_business_repo
        graph.fetch_business_by_id = lambda bid: {"id": bid, "sandbox_config": {}}
        graph.prepare_business_repo = lambda task, business: {
            "success": True,
            "repo_path": "/tmp/.workspaces/biz-x",
            "repo_full_name": "acme/widgets",
            "github_token_secret_name": "ACME_TOKEN",
        }
        try:
            out = graph.resolve_business_repo_if_needed(_state({"id": "t1", "business_id": "biz-x"}))
        finally:
            graph.fetch_business_by_id = original_fetch
            graph.prepare_business_repo = original_prepare
        assert out.stop_reason is None
        assert out.current_task["repo_path"] == "/tmp/.workspaces/biz-x"
        assert out.current_task["business_repo_full_name"] == "acme/widgets"
        assert not failed and not blocked
    _with_temp_runner_dir(body)


def test_node_forbidden_repo_hard_fails():
    def body(outbox, inbox, failed, blocked):
        original_fetch = graph.fetch_business_by_id
        original_prepare = graph.prepare_business_repo
        graph.fetch_business_by_id = lambda bid: {"id": bid, "sandbox_config": {}}
        graph.prepare_business_repo = lambda task, business: {
            "success": False, "reason": "forbidden_repo", "repo_full_name": "bucks-ai/bucks-ai",
        }
        try:
            out = graph.resolve_business_repo_if_needed(_state({"id": "t1", "business_id": "biz-x"}))
        finally:
            graph.fetch_business_by_id = original_fetch
            graph.prepare_business_repo = original_prepare
        assert out.stop_reason == "business_repo_forbidden"
        assert out.current_task.get("repo_path") is None
        assert failed and failed[0][0] == "t1"
    _with_temp_runner_dir(body)


def test_node_missing_secret_blocks_and_writes_resource_request():
    def body(outbox, inbox, failed, blocked):
        original_fetch = graph.fetch_business_by_id
        original_prepare = graph.prepare_business_repo
        graph.fetch_business_by_id = lambda bid: {"id": bid, "sandbox_config": {}}
        graph.prepare_business_repo = lambda task, business: {
            "success": False, "reason": "missing_secret", "secret_name": "ACME_GH_TOKEN",
        }
        try:
            out = graph.resolve_business_repo_if_needed(_state({"id": "t1", "business_id": "biz-x"}))
        finally:
            graph.fetch_business_by_id = original_fetch
            graph.prepare_business_repo = original_prepare
        assert out.stop_reason == "awaiting_resources"
        req_file = outbox / "t1_resource_request.txt"
        assert req_file.exists()
        text = req_file.read_text()
        assert "ACME_GH_TOKEN" in text
        assert "shhh" not in text.lower()  # never a token value, only the name
        assert blocked and blocked[0][0] == "t1"
    _with_temp_runner_dir(body)


def test_node_missing_secret_fulfilled_retries_successfully():
    def body(outbox, inbox, failed, blocked):
        (inbox / "t1_resources_provided.txt").write_text("ok")
        original_fetch = graph.fetch_business_by_id
        original_prepare = graph.prepare_business_repo
        graph.fetch_business_by_id = lambda bid: {"id": bid, "sandbox_config": {}}
        graph.prepare_business_repo = lambda task, business: {
            "success": True,
            "repo_path": "/tmp/.workspaces/biz-x",
            "repo_full_name": "acme/widgets",
            "github_token_secret_name": "ACME_GH_TOKEN",
        }
        try:
            out = graph.resolve_business_repo_if_needed(_state({"id": "t1", "business_id": "biz-x"}))
        finally:
            graph.fetch_business_by_id = original_fetch
            graph.prepare_business_repo = original_prepare
        assert out.stop_reason is None, out.stop_reason
        assert out.current_task["repo_path"] == "/tmp/.workspaces/biz-x"
    _with_temp_runner_dir(body)


def test_node_no_sandbox_config_blocks_as_resource_request():
    def body(outbox, inbox, failed, blocked):
        original_fetch = graph.fetch_business_by_id
        original_prepare = graph.prepare_business_repo
        graph.fetch_business_by_id = lambda bid: {"id": bid, "sandbox_config": None}
        graph.prepare_business_repo = lambda task, business: {"success": False, "reason": "no_sandbox_config"}
        try:
            out = graph.resolve_business_repo_if_needed(_state({"id": "t1", "business_id": "biz-x"}))
        finally:
            graph.fetch_business_by_id = original_fetch
            graph.prepare_business_repo = original_prepare
        assert out.stop_reason == "awaiting_resources"
        req_file = outbox / "t1_resource_request.txt"
        assert req_file.exists()
        assert "sandbox_config" in req_file.read_text()
        assert blocked and blocked[0][0] == "t1"
    _with_temp_runner_dir(body)


# ---------------------------------------------------------------------------
# Routing + wiring
# ---------------------------------------------------------------------------

def test_route_after_business_repo_stops_on_stop_reason():
    assert graph._route_after_business_repo(RunnerState(stop_reason="business_repo_forbidden")) == "decide_continue_or_stop"


def test_route_after_business_repo_proceeds_otherwise():
    assert graph._route_after_business_repo(RunnerState()) == "check_acceptance_criteria"


def test_node_is_wired_into_graph():
    nodes = list(graph.build_graph().get_graph().nodes)
    assert "resolve_business_repo_if_needed" in nodes, nodes


# ---------------------------------------------------------------------------
# Regular (non-business) tasks are never touched by the repo_path override
# ---------------------------------------------------------------------------

def test_effective_repo_path_defaults_to_cfg_for_ordinary_tasks():
    state = RunnerState(current_task={"id": "t1"})
    assert graph._effective_repo_path(state) == graph.cfg.repo_path


def test_effective_repo_path_uses_override_for_business_tasks():
    state = RunnerState(current_task={"id": "t1", "repo_path": "/tmp/.workspaces/biz-x"})
    assert graph._effective_repo_path(state) == "/tmp/.workspaces/biz-x"


if __name__ == "__main__":
    tests = [
        test_workspace_dir_is_under_dot_workspaces,
        test_workspace_dir_sanitizes_path_traversal,
        test_is_bucks_ai_repo_matches_configured_repo,
        test_is_bucks_ai_repo_false_for_other_repo,
        test_is_bucks_ai_repo_fallback_when_github_repo_unset,
        test_is_bucks_ai_repo_empty_input_is_false,
        test_resolve_scoped_github_token_success,
        test_resolve_scoped_github_token_missing,
        test_resolve_scoped_github_token_no_name,
        test_ensure_workspace_clones_when_new,
        test_ensure_workspace_fetches_when_already_cloned,
        test_ensure_workspace_reports_error_on_git_failure,
        test_guard_raises_when_repo_path_equals_bucks_ai_repo,
        test_guard_passes_when_repo_path_differs,
        test_prepare_business_repo_success,
        test_prepare_business_repo_no_sandbox_config,
        test_prepare_business_repo_forbidden_repo,
        test_prepare_business_repo_missing_secret,
        test_prepare_business_repo_workspace_error,
        test_node_noop_when_no_business_id,
        test_node_business_not_found_hard_fails,
        test_node_success_overrides_repo_path,
        test_node_forbidden_repo_hard_fails,
        test_node_missing_secret_blocks_and_writes_resource_request,
        test_node_missing_secret_fulfilled_retries_successfully,
        test_node_no_sandbox_config_blocks_as_resource_request,
        test_route_after_business_repo_stops_on_stop_reason,
        test_route_after_business_repo_proceeds_otherwise,
        test_node_is_wired_into_graph,
        test_effective_repo_path_defaults_to_cfg_for_ordinary_tasks,
        test_effective_repo_path_uses_override_for_business_tasks,
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
