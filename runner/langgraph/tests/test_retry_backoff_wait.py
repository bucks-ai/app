"""Tests for tools.task_tools.next_retry_eta."""
import json
from datetime import datetime, timedelta

import pytest

import tools.task_tools as task_tools


@pytest.fixture
def tasks_path(tmp_path, monkeypatch):
    p = tmp_path / "tasks.local.json"
    monkeypatch.setattr(task_tools, "_tasks_path", p)
    return p


def _iso(minutes_from_now: float) -> str:
    return (datetime.utcnow() + timedelta(minutes=minutes_from_now)).isoformat()


def _write(p, tasks):
    p.write_text(json.dumps(tasks, indent=2))


def test_none_when_no_tasks(tasks_path):
    _write(tasks_path, [])
    assert task_tools.next_retry_eta() is None


def test_none_when_queued_without_backoff(tasks_path):
    _write(tasks_path, [{"id": "t1", "status": "queued"}])
    assert task_tools.next_retry_eta() is None


def test_none_when_backoff_already_expired(tasks_path):
    _write(tasks_path, [{"id": "t1", "status": "queued", "retry_not_before": _iso(-5)}])
    assert task_tools.next_retry_eta() is None


def test_returns_future_backoff(tasks_path):
    eta = _iso(5)
    _write(tasks_path, [{"id": "t1", "status": "queued", "retry_not_before": eta}])
    assert task_tools.next_retry_eta() == eta


def test_returns_earliest_of_several(tasks_path):
    soon, later = _iso(2), _iso(30)
    _write(tasks_path, [
        {"id": "t1", "status": "queued", "retry_not_before": later},
        {"id": "t2", "status": "queued", "retry_not_before": soon},
    ])
    assert task_tools.next_retry_eta() == soon


def test_ignores_non_queued_statuses(tasks_path):
    _write(tasks_path, [
        {"id": "t1", "status": "failed", "retry_not_before": _iso(5)},
        {"id": "t2", "status": "blocked", "retry_not_before": _iso(5)},
        {"id": "t3", "status": "running", "retry_not_before": _iso(5)},
    ])
    assert task_tools.next_retry_eta() is None
