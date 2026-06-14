"""Unit tests for GitHub issue/task sync helpers.

Runs standalone:

    python tests/test_github_task_sync.py
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tools.github_tools as github_tools
import tools.task_tools as task_tools


def _with_temp_tasks(fn):
    original_path = task_tools._tasks_path
    original_legacy = task_tools._tasks_path_legacy
    with tempfile.TemporaryDirectory() as tmp:
        task_tools._tasks_path = Path(tmp) / "tasks.local.json"
        task_tools._tasks_path_legacy = Path(tmp) / "tasks.json"
        try:
            return fn()
        finally:
            task_tools._tasks_path = original_path
            task_tools._tasks_path_legacy = original_legacy


def test_create_or_update_task_from_issue_is_idempotent():
    def run():
        task_tools.save_tasks([])
        issue = {
            "number": 42,
            "title": "Add webhook retry",
            "body": "Retry transient webhook failures.",
            "url": "https://github.test/repo/issues/42",
            "labels": ["backend", "worker:claude"],
        }
        first = github_tools.create_or_update_task_from_issue(issue)
        second = github_tools.create_or_update_task_from_issue({**issue, "title": "Add webhook retries"})
        tasks = task_tools.load_tasks()

        assert first["id"] == "gh-issue-42"
        assert second["title"] == "Add webhook retries"
        assert len(tasks) == 1
        assert tasks[0]["branch"] == "feature/gh-issue-42"
        assert tasks[0]["type"] == "backend"
        assert tasks[0]["preferred_worker"] == "claude"
        assert tasks[0]["issue_url"] == "https://github.test/repo/issues/42"

    _with_temp_tasks(run)


def test_issue_sync_preserves_existing_task_status():
    def run():
        task_tools.save_tasks([
            {
                "id": "gh-issue-7",
                "title": "Old title",
                "status": "running",
                "source": "github_issue",
                "issue_number": 7,
            }
        ])
        github_tools.create_or_update_task_from_issue({
            "number": 7,
            "title": "New title",
            "labels": ["ui"],
        })
        task = task_tools.load_tasks()[0]
        assert task["title"] == "New title"
        assert task["status"] == "running"
        assert task["preferred_worker"] == "codex"

    _with_temp_tasks(run)


def test_sync_open_issues_to_tasks_uses_listed_issues():
    def run():
        task_tools.save_tasks([])
        original = github_tools.list_open_issues
        github_tools.list_open_issues = lambda repo: [
            {"number": 1, "title": "One", "labels": []},
            {"number": 2, "title": "Two", "labels": ["type:backend"]},
        ]
        try:
            result = github_tools.sync_open_issues_to_tasks("owner/repo")
        finally:
            github_tools.list_open_issues = original

        assert result["synced"] == 2
        tasks = task_tools.load_tasks()
        assert [task["id"] for task in tasks] == ["gh-issue-1", "gh-issue-2"]
        assert tasks[1]["type"] == "backend"

    _with_temp_tasks(run)


def test_update_issue_for_task_result_comments_and_closes_on_success():
    calls = []
    original_comment = github_tools.comment_issue
    original_close = github_tools.close_issue
    github_tools.comment_issue = lambda repo, issue, body: calls.append(("comment", repo, issue, body)) or True
    github_tools.close_issue = lambda repo, issue: calls.append(("close", repo, issue)) or True
    try:
        result = github_tools.update_issue_for_task_result(
            "owner/repo",
            {"title": "Ship it", "issue_number": 9},
            "Task: Ship it\nCheck: pass",
            success=True,
            deploy_verdict="ready",
        )
    finally:
        github_tools.comment_issue = original_comment
        github_tools.close_issue = original_close

    assert result["updated"] is True
    assert result["closed"] is True
    assert calls[0][:3] == ("comment", "owner/repo", 9)
    assert "Deploy: ready" in calls[0][3]
    assert calls[1] == ("close", "owner/repo", 9)


def test_update_issue_for_task_result_does_not_close_on_failure():
    calls = []
    original_comment = github_tools.comment_issue
    original_close = github_tools.close_issue
    github_tools.comment_issue = lambda repo, issue, body: calls.append(("comment", repo, issue, body)) or True
    github_tools.close_issue = lambda repo, issue: calls.append(("close", repo, issue)) or True
    try:
        result = github_tools.update_issue_for_task_result(
            "owner/repo",
            {"title": "Ship it", "issue_number": 9},
            "Check: fail",
            success=False,
        )
    finally:
        github_tools.comment_issue = original_comment
        github_tools.close_issue = original_close

    assert result["updated"] is True
    assert result["closed"] is False
    assert len(calls) == 1
    assert "failed" in calls[0][3]


if __name__ == "__main__":
    tests = [
        test_create_or_update_task_from_issue_is_idempotent,
        test_issue_sync_preserves_existing_task_status,
        test_sync_open_issues_to_tasks_uses_listed_issues,
        test_update_issue_for_task_result_comments_and_closes_on_success,
        test_update_issue_for_task_result_does_not_close_on_failure,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except Exception:
            failures += 1
            print(f"✗ {test.__name__}")
            traceback.print_exc()
    if failures:
        raise SystemExit(1)
    print(f"\n{len(tests)} tests passed.")
