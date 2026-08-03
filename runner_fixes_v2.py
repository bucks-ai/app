#!/usr/bin/env python3
"""Apply all runner reliability fixes (v1 + v2) to the current working tree.

Run from the repo root: python3 runner_fixes_v2.py
Idempotent: skips any fix already present. Fails loudly if an anchor is missing.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent / "runner" / "langgraph"
applied, skipped = [], []


def patch(path: pathlib.Path, marker: str, old: str, new: str, name: str):
    s = path.read_text()
    if marker in s:
        skipped.append(name)
        return
    if old not in s:
        sys.exit(f"FAILED: anchor not found for {name} in {path} — file has diverged, do not proceed.")
    path.write_text(s.replace(old, new, 1))
    applied.append(name)


# ── 1. main.py — fresh session per run-loop ─────────────────────────────────
patch(
    ROOT / "main.py",
    "init.stop_reason = None",
    """    saved = read_state()
    init = RunnerState(**{k: v for k, v in saved.items() if k in RunnerState.model_fields})
    if not init.started_at:
        init.started_at = datetime.utcnow().isoformat()
    init.status = "running"

    print("Starting autonomous loop (Ctrl+C to stop)...")""",
    """    saved = read_state()
    init = RunnerState(**{k: v for k, v in saved.items() if k in RunnerState.model_fields})
    # Every run-loop invocation is a fresh session. A stop_reason, loop_count,
    # failure streak, or started_at left over from a previous run would
    # otherwise stop this run on its first cycle (instant "awaiting_resources"
    # / "max_loop_tasks" / "max_runtime" stops after a restart).
    init.stop_reason = None
    init.loop_count = 0
    init.consecutive_failures = 0
    init.started_at = datetime.utcnow().isoformat()
    init.status = "running"

    print("Starting autonomous loop (Ctrl+C to stop)...")""",
    "main.py fresh-session",
)

# ── 2a. task_tools.py — requeue helper ──────────────────────────────────────
patch(
    ROOT / "tools" / "task_tools.py",
    "def requeue_fulfilled_blocked_tasks",
    "def mark_task_blocked(task_id: str, reason: str):",
    '''def requeue_fulfilled_blocked_tasks(inbox_dir) -> list[str]:
    """Requeue blocked tasks whose resource-fulfillment file has landed.

    The resource gate blocks a task and waits for
    ``inbox/{task_id}_resources_provided.txt``. The approvals daemon (or a
    human) creates that file, but nothing flipped the task back to ``queued``
    — so the loop restarted into an empty queue and stalled. This scan closes
    that gap. Only file *existence* is checked; contents are never read.

    Returns the list of requeued task ids.
    """
    inbox_dir = Path(inbox_dir)
    requeued = []
    tasks = load_tasks()
    for task in tasks:
        if task.get("status") != "blocked":
            continue
        task_id = task.get("id")
        if task_id and (inbox_dir / f"{task_id}_resources_provided.txt").exists():
            task["status"] = "queued"
            task["error"] = None
            task["updated_at"] = _now()
            requeued.append(task_id)
    if requeued:
        save_tasks(tasks)
    return requeued


def mark_task_blocked(task_id: str, reason: str):''',
    "task_tools.py requeue helper",
)

# ── 2b. task_tools.py — backoff ETA helper ──────────────────────────────────
patch(
    ROOT / "tools" / "task_tools.py",
    "def next_retry_eta",
    "def mark_task_blocked(task_id: str, reason: str):",
    '''def next_retry_eta() -> Optional[str]:
    """Earliest future ``retry_not_before`` among queued tasks, or None.

    When every queued task is inside its retry-backoff window,
    ``get_next_queued_task`` returns None even though work exists — it's just
    ineligible for a few more seconds. The loop uses this ETA to wait out the
    shortest backoff instead of falling through to the planner and stopping
    with ``chatgpt_no_task``.
    """
    now_iso = _now()
    etas = [
        t["retry_not_before"]
        for t in load_tasks()
        if t.get("status") == "queued"
        and t.get("retry_not_before")
        and t["retry_not_before"] > now_iso
    ]
    return min(etas) if etas else None


def mark_task_blocked(task_id: str, reason: str):''',
    "task_tools.py backoff ETA helper",
)

# ── 3a. graph.py — imports (handles both v1-present and fresh files) ────────
gp = ROOT / "graph.py"
s = gp.read_text()
if "next_retry_eta," in s:
    skipped.append("graph.py imports")
elif "requeue_fulfilled_blocked_tasks," in s:
    s = s.replace("    requeue_fulfilled_blocked_tasks,",
                  "    next_retry_eta,\n    requeue_fulfilled_blocked_tasks,", 1)
    gp.write_text(s); applied.append("graph.py imports (added next_retry_eta)")
elif "    mark_task_blocked,\n    requeue_task," in s:
    s = s.replace("    mark_task_blocked,\n    requeue_task,",
                  "    mark_task_blocked,\n    next_retry_eta,\n    requeue_fulfilled_blocked_tasks,\n    requeue_task,", 1)
    gp.write_text(s); applied.append("graph.py imports (added both)")
else:
    sys.exit("FAILED: graph.py import anchor not found — do not proceed.")

# ── 3b. graph.py — load_next_task: requeue scan ─────────────────────────────
patch(
    gp,
    "resource_request_fulfilled_requeued",
    """def load_next_task(state: RunnerState) -> RunnerState:
    task = get_next_queued_task()""",
    """def load_next_task(state: RunnerState) -> RunnerState:
    # Auto-requeue any blocked task whose resource fulfillment file has
    # landed in inbox/ (written by the approvals daemon or by hand).
    for _tid in requeue_fulfilled_blocked_tasks(_RUNNER_DIR / "inbox"):
        log_event("resource_request_fulfilled_requeued", {
            "task_id": _tid,
            "message": "fulfillment file found in inbox/; task requeued",
        }, task_id=_tid)
    task = get_next_queued_task()""",
    "graph.py requeue scan",
)

# ── 3c. graph.py — load_next_task: backoff wait ─────────────────────────────
patch(
    gp,
    "retry_backoff_waiting",
    """        }, task_id=_tid)
    task = get_next_queued_task()""",
    """        }, task_id=_tid)
    task = get_next_queued_task()
    if not task:
        # Every queued task may simply be inside its retry-backoff window —
        # there IS work, it's just ineligible for a few more seconds. Wait
        # out the shortest backoff (capped at 30 min) instead of falling
        # through to the planner and stopping the loop with chatgpt_no_task.
        eta = next_retry_eta()
        if eta:
            try:
                remaining = (datetime.fromisoformat(eta) - datetime.utcnow()).total_seconds()
            except (ValueError, TypeError):
                remaining = 0
            if 0 < remaining <= 1800:
                log_event("retry_backoff_waiting", {
                    "resume_at": eta,
                    "wait_seconds": round(remaining, 1),
                })
                time.sleep(remaining + 1)
                task = get_next_queued_task()""",
    "graph.py backoff wait",
)

# ── 4. log_tools.py — never fan out to Slack from inside pytest ─────────────
# (Guard lives in the flight recorder's fan-out, NOT in slack_tools.notify_event:
#  test_slack_tools legitimately asserts notify_event's return values.)
patch(
    ROOT / "tools" / "log_tools.py",
    "PYTEST_CURRENT_TEST",
    """    try:
        from tools.slack_tools import notify_event
        notify_event(event_type, payload, task_id)
    except Exception:
        pass""",
    """    try:
        from tools.slack_tools import notify_event
        # Never fan out to the REAL Slack channel from inside the test suite:
        # mocked failures ("simulated db error", "connection refused", ...)
        # logged by code under test would otherwise ping the team channel on
        # every check.sh / pytest run. config's load_dotenv() resurrects .env
        # values, so env-stripping in conftest.py alone is not sufficient.
        # A test-provided stub (monkeypatched onto slack_tools) has a
        # different __module__, so tests that assert the fan-out still work.
        if (
            os.environ.get("PYTEST_CURRENT_TEST")
            and getattr(notify_event, "__module__", "") == "tools.slack_tools"
        ):
            return
        notify_event(event_type, payload, task_id)
    except Exception:
        pass""",
    "log_tools.py pytest guard",
)

# ── 5 & 6. New test files ────────────────────────────────────────────────────
NEW_FILES = {
    ROOT / "tests" / "conftest.py": '''"""Test-session guards.

The runner's flight recorder (log_tools.log_event) fans every event out to
Slack via notify_event. When pytest runs in a shell where .env has been
exported (set -a; source .env), SLACK_WEBHOOK_URL is set — so mocked failures
from the test suite ("simulated db error", "connection refused", ...) were
posted to the real team Slack channel on every check run. These fixtures make
the test suite integration-silent.
"""
import os
import pytest

_LIVE_VARS = ("SLACK_WEBHOOK_URL", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN")

# Strip live-integration env before any test imports build the cached config.
for _v in _LIVE_VARS:
    os.environ.pop(_v, None)
os.environ["SLACK_NOTIFY"] = "false"


@pytest.fixture(autouse=True)
def _no_live_slack(monkeypatch):
    for v in _LIVE_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("SLACK_NOTIFY", "false")
''',
    ROOT / "tests" / "test_resource_requeue.py": '''"""Tests for tools.task_tools.requeue_fulfilled_blocked_tasks."""
import json

import pytest

import tools.task_tools as task_tools


@pytest.fixture
def queue(tmp_path, monkeypatch):
    tasks_path = tmp_path / "tasks.local.json"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    monkeypatch.setattr(task_tools, "_tasks_path", tasks_path)
    return tasks_path, inbox


def _write(tasks_path, tasks):
    tasks_path.write_text(json.dumps(tasks, indent=2))


def _statuses(tasks_path):
    return {t["id"]: t["status"] for t in json.loads(tasks_path.read_text())}


def test_requeues_blocked_task_with_fulfillment_file(queue):
    tasks_path, inbox = queue
    _write(tasks_path, [{"id": "t1", "status": "blocked", "error": "awaiting resources"}])
    (inbox / "t1_resources_provided.txt").touch()
    assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == ["t1"]
    assert _statuses(tasks_path)["t1"] == "queued"


def test_blocked_task_without_file_stays_blocked(queue):
    tasks_path, inbox = queue
    _write(tasks_path, [{"id": "t1", "status": "blocked", "error": "awaiting resources"}])
    assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == []
    assert _statuses(tasks_path)["t1"] == "blocked"


def test_non_blocked_tasks_untouched(queue):
    tasks_path, inbox = queue
    _write(tasks_path, [
        {"id": "t1", "status": "queued"},
        {"id": "t2", "status": "complete"},
        {"id": "t3", "status": "failed", "error": "boom"},
    ])
    for tid in ("t1", "t2", "t3"):
        (inbox / f"{tid}_resources_provided.txt").touch()
    assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == []
    assert _statuses(tasks_path) == {"t1": "queued", "t2": "complete", "t3": "failed"}


def test_mixed_queue_only_fulfilled_requeued(queue):
    tasks_path, inbox = queue
    _write(tasks_path, [
        {"id": "a", "status": "blocked", "error": "awaiting resources"},
        {"id": "b", "status": "blocked", "error": "awaiting resources"},
        {"id": "c", "status": "queued"},
    ])
    (inbox / "a_resources_provided.txt").touch()
    assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == ["a"]
    statuses = _statuses(tasks_path)
    assert statuses == {"a": "queued", "b": "blocked", "c": "queued"}
    task_a = [t for t in json.loads(tasks_path.read_text()) if t["id"] == "a"][0]
    assert task_a["error"] is None
''',
    ROOT / "tests" / "test_retry_backoff_wait.py": '''"""Tests for tools.task_tools.next_retry_eta."""
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
''',
}

for path, content in NEW_FILES.items():
    if path.exists():
        skipped.append(f"{path.name} (exists)")
    else:
        path.write_text(content)
        applied.append(path.name)

print("Applied:", ", ".join(applied) or "nothing")
print("Skipped (already present):", ", ".join(skipped) or "none")
print("\nNow run:  cd runner/langgraph && python -m pytest tests/ -x -q")
