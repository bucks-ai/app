"""Task queue backed by tasks.json.

Every read goes through ``load_tasks`` and every write through ``save_tasks``,
which is what makes the M4c.0 integrity guarantees hold for the whole runner:

- **Auto-repair on load.** Impossible states (an orphaned ``running``, colliding
  ids, a terminal task holding a retry window, an unknown status) are repaired
  in memory and persisted, each class logged as its own event. See
  ``tools/task_schema.py`` for the rules; this module supplies the parts that
  cannot be pure — the clock, the host, and process liveness.
- **Validation on save.** Violations are logged loudly but never block the
  write: refusing to persist would strand the runner mid-task, which is the
  failure mode this work exists to remove.
- **Atomic writes.** A save is a temp-file write plus ``os.replace``, so an
  interrupted process can never leave a truncated queue behind. Before M4c.0 a
  ``write_text`` that died halfway through would take the whole queue with it.
"""
import json
import os
import socket
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from tools.task_schema import (
    ORPHAN_GRACE_SECONDS,
    repair_tasks,
    validate_tasks,
    validate_transition,
)

_BACKOFF_SKIPPED_STATUS = "queued"  # only queued tasks participate in backoff

_tasks_path = Path(__file__).parent.parent / ".runtime" / "tasks.local.json"
_tasks_path_legacy = Path(__file__).parent.parent / "tasks.json"

#: The real, operator-owned queue. Tests redirect ``_tasks_path`` to a temp
#: file; this constant stays pointed at the live one so writes to it can be
#: recognised and refused from inside the test suite.
_REAL_TASKS_PATH = _tasks_path

_DEFAULT_TASKS = [
    {
        "id": "operating-team-ui",
        "title": "Build Operating Team UI",
        "type": "ui",
        "preferred_worker": "codex",
        "branch": "feature/operating-team-ui",
        "status": "queued",
    }
]


def _ensure_tasks_file():
    _tasks_path.parent.mkdir(parents=True, exist_ok=True)
    if not _tasks_path.exists():
        # Migrate legacy tasks.json → .runtime/tasks.local.json on first run
        if _tasks_path_legacy.exists():
            import shutil
            shutil.copy2(_tasks_path_legacy, _tasks_path)
        else:
            _tasks_path.write_text(json.dumps(_DEFAULT_TASKS, indent=2))


def _now() -> str:
    return datetime.utcnow().isoformat()


def _log(event_type: str, payload: dict, task_id: Optional[str] = None):
    """Log via the flight recorder, lazily imported to avoid an import cycle.

    Never allowed to break a queue read or write: the queue is the runner's
    only durable record of what it is supposed to do.
    """
    try:
        from tools.log_tools import log_event
        log_event(event_type, payload, task_id)
    except Exception:
        pass


def _pid_alive(pid: int) -> bool:
    """True when a process with *pid* exists on this host.

    ``os.kill(pid, 0)`` sends no signal — it only asks the kernel whether the
    process exists. ``PermissionError`` means it exists but belongs to another
    user, which still counts as alive.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def live_task_ids() -> set:
    """Task ids the current runner session claims to be executing.

    Read from ``.runtime/state.local.json``. This covers rows written before
    M4c.0 that carry no owner pid: the session that is actually working on
    them still names them, so they are never mistaken for orphans.
    """
    try:
        from tools.log_tools import read_state
        state = read_state() or {}
    except Exception:
        return set()
    if state.get("status") != "running":
        return set()
    current = state.get("current_task_id")
    return {current} if current else set()


def _atomic_write_json(path: Path, data) -> None:
    """Write *data* as JSON so readers only ever see a whole file.

    Writes a sibling temp file, flushes it to disk, then ``os.replace``s it
    over the target — an atomic rename within the same filesystem. A process
    killed mid-save leaves either the previous queue or the new one, never a
    half-written list.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        with open(tmp_path, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _persist_queue(tasks: list) -> bool:
    """Write the queue, unless doing so would clobber live state from a test.

    A test that forgets to redirect ``_tasks_path`` used to be harmless — reads
    were reads. Now that a load repairs and a save validates, an unredirected
    test would rewrite the founder's real queue mid-run. Same reasoning (and
    same mechanism) as the Slack fan-out guard in ``log_tools``: the test suite
    must never reach live state. Returns True when the write happened.
    """
    if os.environ.get("PYTEST_CURRENT_TEST") and _tasks_path == _REAL_TASKS_PATH:
        _log("task_queue_write_skipped_in_tests", {"path": _tasks_path.name})
        return False
    _atomic_write_json(_tasks_path, tasks)
    return True


def load_tasks(*, repair: bool = True) -> list[dict]:
    """Load the queue, repairing impossible states on the way through.

    Repairs are persisted immediately (atomically) and each class is logged as
    its own ``task_queue_repaired`` event, so the founder can see in the log
    exactly what was wrong instead of discovering it by reading JSON. Pass
    ``repair=False`` to see the file as it actually is — ``doctor`` does this
    so it can report damage before deciding to fix it.
    """
    _ensure_tasks_file()
    try:
        tasks = json.loads(_tasks_path.read_text())
    except json.JSONDecodeError as exc:
        # A corrupt queue must not take the loop down with it, but it must not
        # be silently replaced either: keep the bytes for forensics.
        salvage = _tasks_path.with_name(f"{_tasks_path.name}.corrupt.{_now().replace(':', '')}")
        salvage.write_text(_tasks_path.read_text())
        _log("task_queue_unreadable", {"error": str(exc), "salvaged_to": salvage.name})
        _persist_queue([])
        return []

    if not repair:
        return tasks

    repaired, repairs = repair_tasks(
        tasks,
        live_task_ids=live_task_ids(),
        host=socket.gethostname(),
        pid_alive=_pid_alive,
        grace_seconds=ORPHAN_GRACE_SECONDS,
        now_iso=_now(),
    )
    if repairs:
        for fix in repairs:
            _log("task_queue_repaired", fix, fix.get("task_id"))
        _log("task_queue_repair_summary", {
            "repair_count": len(repairs),
            "kinds": sorted({fix["kind"] for fix in repairs}),
            "task_count_before": len(tasks) if isinstance(tasks, list) else 0,
            "task_count_after": len(repaired),
        })
        _persist_queue(repaired)
    return repaired


def save_tasks(tasks: list[dict]):
    """Persist the queue atomically, logging any schema violation it carries.

    Validation never blocks the write. A save that refuses leaves the runner's
    in-memory state and its durable state disagreeing — which is precisely the
    class of bug this module exists to end.
    """
    violations = validate_tasks(tasks)
    if violations:
        _log("task_schema_violation", {
            "violation_count": len(violations),
            "kinds": sorted({v["kind"] for v in violations}),
            "violations": violations[:20],
        })
    _persist_queue(tasks)


def find_task_by_id(task_id: str) -> Optional[dict]:
    for task in load_tasks():
        if task.get("id") == task_id:
            return task
    return None


def find_task_by_github_issue(issue_number: int) -> Optional[dict]:
    for task in load_tasks():
        if task.get("source") == "github_issue" and task.get("issue_number") == issue_number:
            return task
    return None


def get_next_queued_task() -> Optional[dict]:
    """Return the first queued task whose retry backoff window has expired.

    Tasks with a ``retry_not_before`` timestamp that is still in the future
    are skipped so the runner waits out the backoff rather than immediately
    hitting the same degraded condition again.
    """
    now_iso = _now()
    tasks = load_tasks()
    for task in tasks:
        if task.get("status") != "queued":
            continue
        retry_not_before = task.get("retry_not_before")
        if retry_not_before and retry_not_before > now_iso:
            continue
        return task
    return None


def _set_status(task_id: str, new_status: str, fields: Optional[dict] = None) -> bool:
    """Move *task_id* to *new_status*, enforcing the allowed-transition table.

    A rejected transition (the only ones are leaving ``complete``/``failed``
    for anything other than an explicit requeue) is logged as
    ``task_transition_rejected`` and skipped, so a late or duplicated write
    cannot re-open a task the runner already finished.

    Returns True when at least one record changed.
    """
    tasks = load_tasks()
    changed = False
    for task in tasks:
        if task.get("id") != task_id:
            continue
        old_status = task.get("status")
        if not validate_transition(old_status, new_status):
            _log("task_transition_rejected", {
                "task_id": task_id,
                "from": old_status,
                "to": new_status,
                "detail": f"'{old_status}' -> '{new_status}' is not an allowed transition",
            }, task_id)
            continue
        task["status"] = new_status
        task.update(fields or {})
        task["updated_at"] = _now()
        if new_status == "running":
            # Stamp the owning process so an interrupted run is provably
            # orphaned on the next load rather than guessed at.
            task["owner_pid"] = os.getpid()
            task["owner_host"] = socket.gethostname()
        else:
            task.pop("owner_pid", None)
            task.pop("owner_host", None)
        changed = True
    if changed:
        save_tasks(tasks)
    return changed


def mark_task_running(task_id: str):
    _set_status(task_id, "running")


def mark_task_complete(task_id: str, summary: str):
    _set_status(task_id, "complete", {"summary": summary})


def mark_task_failed(task_id: str, error: str):
    _set_status(task_id, "failed", {"error": error})


# Inbox files that unblock a task, one per human-approval gate. Existence is the
# whole signal — contents are never read (AGENTS.md: the resources file is a
# human-only fulfillment marker and must stay opaque).
_UNBLOCK_FILE_SUFFIXES = (
    "_resources_provided.txt",   # resource & credential gate
    "_merge_approved.txt",       # risk-based merge approval gate
)


def requeue_fulfilled_blocked_tasks(inbox_dir) -> list[str]:
    """Requeue blocked tasks whose human-approval file has landed.

    A task-scoped gate blocks its task and waits for a file under ``inbox/``:
    the resource gate for ``{task_id}_resources_provided.txt``, the merge
    approval gate for ``{task_id}_merge_approved.txt``. The approvals daemon (or
    a human) creates that file, but nothing flipped the task back to ``queued``
    — so the loop restarted into an empty queue and stalled. This scan closes
    that gap. Only file *existence* is checked; contents are never read.

    Each fulfillment file unblocks a task **once**. Since M4c.0 a task-scoped
    gate block no longer stops the run, so a task that blocks again for the same
    reason after being requeued (the human signalled fulfillment but the
    credential still isn't resolvable) would otherwise be requeued, re-run, and
    re-blocked forever, burning the whole loop. ``unblock_requeued_at`` records
    that the signal has been consumed; clearing it (or deleting the inbox file
    and re-creating it after fixing the credential) allows another attempt.

    Returns the list of requeued task ids.
    """
    inbox_dir = Path(inbox_dir)
    requeued = []
    tasks = load_tasks()
    for task in tasks:
        if task.get("status") != "blocked" or task.get("unblock_requeued_at"):
            continue
        task_id = task.get("id")
        if task_id and any(
            (inbox_dir / f"{task_id}{suffix}").exists() for suffix in _UNBLOCK_FILE_SUFFIXES
        ):
            task["status"] = "queued"
            task["error"] = None
            task["updated_at"] = _now()
            task["unblock_requeued_at"] = task["updated_at"]
            requeued.append(task_id)
    if requeued:
        save_tasks(tasks)
    return requeued


def next_retry_eta() -> Optional[str]:
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


def mark_task_blocked(task_id: str, reason: str):
    """Mark a task as blocked on a human action (e.g. awaiting resources).

    Distinct from ``failed`` so the task isn't lost as a failure: a human can
    provision what's needed and flip it back to ``queued`` to retry.
    """
    _set_status(task_id, "blocked", {"error": reason})


def requeue_task(
    task_id: str,
    retry_count: int,
    retry_not_before: Optional[str] = None,
    fields: Optional[dict] = None,
):
    """Requeue a failed task for another attempt (status → ``queued``).

    Records ``retry_count`` so the failure guard can cap how many times a task is
    retried before it is marked permanently ``failed``.  When ``retry_not_before``
    is supplied (an ISO-8601 UTC timestamp), ``get_next_queued_task`` skips this
    task until that time has passed — implementing backoff for degraded workers.

    ``fields`` carries extra values to persist alongside the requeue — used by
    the transient-failure path (m4c-03) to bump ``transient_retry_count``, which
    is counted separately from ``retry_count`` precisely so an unreachable
    network never spends the budget that decides whether a task may be failed.
    """
    tasks = load_tasks()
    changed = False
    for task in tasks:
        if task.get("id") != task_id:
            continue
        task["status"] = "queued"
        task["retry_count"] = retry_count
        task.update(fields or {})
        task["updated_at"] = _now()
        task.pop("owner_pid", None)
        task.pop("owner_host", None)
        if retry_not_before:
            task["retry_not_before"] = retry_not_before
        else:
            task.pop("retry_not_before", None)
        changed = True
    if changed:
        save_tasks(tasks)


def update_task_branch(task_id: str, branch: str):
    """Persist a rewritten branch name back to tasks.json for the given task."""
    tasks = load_tasks()
    for task in tasks:
        if task.get("id") == task_id:
            task["branch"] = branch
            task["updated_at"] = _now()
    save_tasks(tasks)


def remove_tasks(task_ids) -> list[str]:
    """Delete tasks by id, refusing to delete one a worker is running.

    Used by the m4c-03 self-healing paths that prune records rather than
    repair them: fixture placeholders, and local rows whose Supabase
    ``mission_tasks`` parent no longer exists. Returns the ids actually
    removed, so the caller logs what happened rather than what it asked for.
    """
    wanted = {t for t in (task_ids or []) if t}
    if not wanted:
        return []
    tasks = load_tasks()
    removed = [
        t.get("id") for t in tasks
        if t.get("id") in wanted and t.get("status") != "running"
    ]
    if not removed:
        return []
    save_tasks([t for t in tasks if t.get("id") not in set(removed)])
    return removed


def add_task(task: dict):
    tasks = load_tasks()
    if "id" not in task:
        task["id"] = str(uuid.uuid4())[:8]
    task.setdefault("status", "queued")
    task.setdefault("created_at", _now())
    tasks.append(task)
    save_tasks(tasks)


def upsert_task(task: dict, *, preserve_status: bool = True) -> dict:
    """Insert or update a task by id, or by linked GitHub issue.

    GitHub issue sync can run repeatedly. This keeps the local queue idempotent
    while still refreshing mutable issue fields such as title, labels, and URL.
    Existing execution state is preserved by default so a completed or running
    task is not requeued just because its issue is still open.
    """
    tasks = load_tasks()
    incoming = dict(task)
    if "id" not in incoming:
        incoming["id"] = str(uuid.uuid4())[:8]

    match_idx = None
    for idx, existing in enumerate(tasks):
        if existing.get("id") == incoming.get("id"):
            match_idx = idx
            break
        if (
            incoming.get("source") == "github_issue"
            and existing.get("source") == "github_issue"
            and incoming.get("issue_number") is not None
            and existing.get("issue_number") == incoming.get("issue_number")
        ):
            match_idx = idx
            break

    now = _now()
    if match_idx is None:
        incoming.setdefault("status", "queued")
        incoming.setdefault("created_at", now)
        incoming["updated_at"] = now
        tasks.append(incoming)
        save_tasks(tasks)
        return incoming

    existing = tasks[match_idx]
    merged = {**existing, **incoming}
    if preserve_status:
        merged["status"] = existing.get("status", incoming.get("status", "queued"))
    merged.setdefault("created_at", existing.get("created_at") or now)
    merged["updated_at"] = now
    tasks[match_idx] = merged
    save_tasks(tasks)
    return merged
