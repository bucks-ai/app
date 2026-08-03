"""Schema, invariants, and auto-repair for the local task queue.

``.runtime/tasks.local.json`` is a plain JSON list mutated by a long-running
process. Until M4c.0 it had no schema, no invariants, and no repair — so every
state the runner could create but not exit was fixed by hand-editing the file
(five times during M4b). The three recurring shapes:

- **Orphaned ``running``** — an interrupted run leaves the in-flight task at
  ``running`` forever. Nothing owns it, nothing requeues it, and the next loop
  sees zero ``queued`` work and exits looking "done".
- **Colliding ids** — "Execute: AI Infra" was seeded three times, producing
  three rows sharing each id. Status writes key off ``id``, so a completion
  could land on the wrong row.
- **Stale backoff on a finished task** — a ``retry_not_before`` left behind on
  a row that has already reached a terminal state; meaningless, and misleading
  in every health report that reads it.

This module is the DATA layer for those failures: it defines what a task
record *is*, which state transitions are possible, and how an impossible state
is repaired. It is intentionally pure — no file, no network, no clock, no
process inspection. Liveness (``is_pid_alive``) and the current time are
injected by the caller (``tools/task_tools.py``), which keeps every rule here
unit-testable without a filesystem.

Boundary with m4c-03 (graph-level state self-healing): m4c-03 owns *policy* —
when to reconcile against Supabase, how to classify a transient error, when a
mission may be re-seeded. This module owns *structure* — what a valid record
is and how an already-broken file is made valid again. m4c-03 calls into here;
nothing here reaches back up into the graph.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Iterable, Optional

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

#: Every status the runner is allowed to write.
STATUSES = frozenset({"queued", "running", "complete", "failed", "blocked"})

#: Statuses the runner will never dispatch from again on its own. ``blocked``
#: is deliberately NOT terminal: it is a parked task awaiting a human action,
#: and ``requeue_fulfilled_blocked_tasks`` returns it to ``queued``.
TERMINAL_STATUSES = frozenset({"complete", "failed"})

#: A record missing one of these cannot be dispatched or tracked at all.
REQUIRED_FIELDS = ("id", "title", "status")

#: Known fields and their expected Python types. Unknown keys are allowed —
#: tools bolt on their own metadata (``completion_evidence``, ``dry_run``,
#: ``dedupe_note``, …) and this layer must not fight them. Only a known field
#: carrying the wrong type is a violation.
FIELD_TYPES: dict[str, tuple] = {
    "id": (str,),
    "title": (str,),
    "status": (str,),
    "type": (str,),
    "branch": (str,),
    "preferred_worker": (str,),
    "description": (str,),
    "summary": (str,),
    "error": (str,),
    "source": (str,),
    "mission": (str,),
    "seeded_mission_id": (str,),
    "seeded_task_id": (str,),
    "retry_not_before": (str,),
    "created_at": (str,),
    "updated_at": (str,),
    "retry_count": (int,),
    "issue_number": (int,),
    "owner_pid": (int,),
    "owner_host": (str,),
}

#: Allowed status transitions. Permissive by design for forward motion, strict
#: about leaving a terminal state: the only way out of ``complete``/``failed``
#: is an explicit requeue. That is what stops a late node from re-opening a
#: finished task, or a stale write from resurrecting one as ``running``.
ALLOWED_TRANSITIONS: dict[str, frozenset] = {
    "queued": frozenset({"queued", "running", "blocked", "failed", "complete"}),
    "running": frozenset({"running", "queued", "blocked", "failed", "complete"}),
    "blocked": frozenset({"blocked", "queued", "running", "failed", "complete"}),
    "failed": frozenset({"failed", "queued", "blocked"}),
    "complete": frozenset({"complete", "queued"}),
}

#: How long a ``running`` task with no owner record may sit before it is
#: treated as orphaned. Rows written before M4c.0 carry no ``owner_pid``, so
#: liveness cannot be proven for them either way — the grace window is the
#: tiebreaker. Sized well above the longest task duration observed in the M4c.0
#: calibration data (41.1 min) so a slow-but-healthy task is never stolen from
#: the loop that is running it. Rows written *after* M4c.0 carry an owner pid
#: and are resolved exactly, without waiting out this window.
ORPHAN_GRACE_SECONDS = 3600


def _parse_iso(value) -> Optional[datetime]:
    """Parse a runner timestamp (naive UTC ``datetime.utcnow().isoformat()``)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


def validate_transition(old_status: Optional[str], new_status: str) -> bool:
    """True when ``old_status`` → ``new_status`` is a transition we allow.

    An unknown or absent ``old_status`` is permissive: the record is already
    broken and repair, not rejection, is the answer for it.
    """
    if new_status not in STATUSES:
        return False
    if old_status is None or old_status not in ALLOWED_TRANSITIONS:
        return True
    return new_status in ALLOWED_TRANSITIONS[old_status]


def validate_task(task, index: int = 0) -> list[dict]:
    """Return the schema violations for a single record (empty when valid).

    Each violation is ``{"kind", "task_id", "field", "detail"}``. Violations
    are reported, never raised: a malformed row must still be visible in
    ``doctor`` output rather than crashing the loop that loads the queue.
    """
    violations: list[dict] = []

    def add(kind, field, detail):
        violations.append({
            "kind": kind,
            "task_id": (task.get("id") if isinstance(task, dict) else None) or f"<index {index}>",
            "field": field,
            "detail": detail,
        })

    if not isinstance(task, dict):
        return [{
            "kind": "not_an_object",
            "task_id": f"<index {index}>",
            "field": None,
            "detail": f"expected a JSON object, found {type(task).__name__}",
        }]

    for field in REQUIRED_FIELDS:
        value = task.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            add("missing_required_field", field, f"'{field}' is required and must be non-empty")

    status = task.get("status")
    if isinstance(status, str) and status and status not in STATUSES:
        add("unknown_status", "status", f"'{status}' is not one of {sorted(STATUSES)}")

    for field, types in FIELD_TYPES.items():
        value = task.get(field)
        if value is None or field not in task:
            continue
        # bool is an int subclass; a boolean retry_count is a bug, not a count.
        if isinstance(value, bool) and bool not in types:
            add("wrong_field_type", field, f"'{field}' should be {types[0].__name__}, found bool")
        elif not isinstance(value, types):
            add(
                "wrong_field_type",
                field,
                f"'{field}' should be {types[0].__name__}, found {type(value).__name__}",
            )

    if isinstance(task.get("retry_count"), int) and not isinstance(task.get("retry_count"), bool):
        if task["retry_count"] < 0:
            add("invalid_field_value", "retry_count", "retry_count must be >= 0")

    if "retry_not_before" in task and task["retry_not_before"] is not None:
        if isinstance(task["retry_not_before"], str) and _parse_iso(task["retry_not_before"]) is None:
            add("invalid_field_value", "retry_not_before", "not a parseable ISO-8601 timestamp")
        if status in TERMINAL_STATUSES:
            add(
                "retry_window_on_terminal_task",
                "retry_not_before",
                f"a '{status}' task cannot be waiting on a retry window",
            )

    return violations


def validate_tasks(tasks) -> list[dict]:
    """Return every schema and cross-record violation in the queue.

    Cross-record rules: ids must be globally unique (status writes key off
    ``id``, so a collision makes every write ambiguous), and one Supabase
    ``mission_tasks`` row must map to at most one local record.
    """
    if not isinstance(tasks, list):
        return [{
            "kind": "queue_not_a_list",
            "task_id": None,
            "field": None,
            "detail": f"tasks file must contain a JSON list, found {type(tasks).__name__}",
        }]

    violations: list[dict] = []
    for index, task in enumerate(tasks):
        violations.extend(validate_task(task, index))

    for id_value, rows in _group_by(tasks, "id").items():
        if len(rows) > 1:
            violations.append({
                "kind": "duplicate_id",
                "task_id": id_value,
                "field": "id",
                "detail": f"{len(rows)} records share id '{id_value}'; status writes are ambiguous",
            })

    for seeded_id, rows in _group_by(tasks, "seeded_task_id").items():
        if len(rows) > 1:
            violations.append({
                "kind": "duplicate_seeded_task_id",
                "task_id": seeded_id,
                "field": "seeded_task_id",
                "detail": (
                    f"{len(rows)} records point at the same Supabase mission_tasks row "
                    f"'{seeded_id}' (ids: {[r.get('id') for r in rows]})"
                ),
            })

    return violations


def _group_by(tasks: Iterable, field: str) -> dict:
    groups: dict = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        value = task.get(field)
        if not isinstance(value, str) or not value.strip():
            continue
        groups.setdefault(value, []).append(task)
    return groups


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------

def classify_running_task(
    task: dict,
    *,
    live_task_ids: Iterable[str] = (),
    now: Optional[datetime] = None,
    host: Optional[str] = None,
    pid_alive: Optional[Callable[[int], bool]] = None,
    grace_seconds: int = ORPHAN_GRACE_SECONDS,
) -> dict:
    """Decide whether a ``running`` task still has a live session owner.

    Returns ``{"live": bool, "reason": str}``. Every ambiguous case resolves to
    ``live`` — requeueing a task that a healthy loop is still executing would
    run the same work twice, which is worse than leaving one stranded row for
    ``doctor`` to surface.

    Resolution order:
      1. The caller says this id is in flight (the current session's state
         file) → live.
      2. The row names an owner process on *this* host → alive means live,
         gone means orphaned. This is the exact case, and the one every row
         written after M4c.0 falls into.
      3. The row names an owner on another host → unverifiable → live.
      4. No owner record at all (pre-M4c.0 row) → orphaned only once it has
         been untouched for ``grace_seconds``. With no timestamp either there
         is nothing to measure, so it stays live and ``doctor`` reports it.
    """
    now = now or datetime.utcnow()
    task_id = task.get("id")
    if task_id and task_id in set(live_task_ids):
        return {"live": True, "reason": "claimed_by_current_session"}

    owner_pid = task.get("owner_pid")
    if isinstance(owner_pid, int) and not isinstance(owner_pid, bool) and owner_pid > 0:
        owner_host = task.get("owner_host")
        if host is not None and owner_host and owner_host != host:
            return {"live": True, "reason": "owner_on_other_host"}
        if pid_alive is None:
            return {"live": True, "reason": "liveness_unverifiable"}
        if pid_alive(owner_pid):
            return {"live": True, "reason": "owner_process_alive"}
        return {"live": False, "reason": "owner_process_gone"}

    updated = _parse_iso(task.get("updated_at")) or _parse_iso(task.get("created_at"))
    if updated is None:
        return {"live": True, "reason": "no_owner_record_unverifiable"}
    if now - updated > timedelta(seconds=grace_seconds):
        return {"live": False, "reason": "no_owner_record_stale"}
    return {"live": True, "reason": "no_owner_record_within_grace"}


#: "Live" verdicts that are really "we could not prove otherwise". Auto-repair
#: leaves these alone; ``doctor`` lists them so a human can see what the
#: automatic pass could not decide on its own.
UNVERIFIABLE_REASONS = frozenset({
    "owner_on_other_host",
    "liveness_unverifiable",
    "no_owner_record_unverifiable",
})


def classify_running_tasks(tasks: list, **kwargs) -> dict:
    """Bucket every ``running`` row into live / orphaned / unverifiable.

    Each entry is ``{"task_id", "reason", "updated_at"}``.
    """
    buckets: dict[str, list] = {"live": [], "orphaned": [], "unverifiable": []}
    for task in tasks:
        if not isinstance(task, dict) or task.get("status") != "running":
            continue
        verdict = classify_running_task(task, **kwargs)
        if not verdict["live"]:
            bucket = "orphaned"
        elif verdict["reason"] in UNVERIFIABLE_REASONS:
            bucket = "unverifiable"
        else:
            bucket = "live"
        buckets[bucket].append({
            "task_id": task.get("id"),
            "reason": verdict["reason"],
            "updated_at": task.get("updated_at"),
        })
    return buckets


def find_orphaned_running(tasks: list, **kwargs) -> list[dict]:
    """Return ``{"task_id", "reason", "updated_at"}`` for each orphaned row."""
    return classify_running_tasks(tasks, **kwargs)["orphaned"]


# ---------------------------------------------------------------------------
# Duplicate resolution
# ---------------------------------------------------------------------------

#: How much work a row represents, used to pick the survivor when two rows are
#: the same task. Higher wins. A ``complete`` row outranks everything: losing
#: it would re-run finished work, the most expensive possible mistake here.
_PROGRESS_RANK = {"complete": 5, "failed": 4, "blocked": 3, "running": 2, "queued": 1}


def progress_score(task: dict) -> tuple:
    """Sort key expressing "which of these rows actually did something".

    Ordered by: status rank, then hard evidence of work (a summary, a
    completion-evidence record, a retry history), then recency. Purely
    comparative — the absolute numbers mean nothing outside a tie-break.
    """
    status = task.get("status") if isinstance(task.get("status"), str) else ""
    evidence = sum([
        1 if task.get("summary") else 0,
        1 if task.get("completion_evidence") else 0,
        1 if task.get("error") else 0,
    ])
    retry_count = task.get("retry_count") if isinstance(task.get("retry_count"), int) else 0
    updated = _parse_iso(task.get("updated_at")) or datetime.min
    return (_PROGRESS_RANK.get(status, 0), evidence, retry_count, updated)


def _dedupe_group(rows: list) -> tuple:
    """Split rows for one duplicate group into (winner, losers)."""
    ordered = sorted(rows, key=progress_score, reverse=True)
    return ordered[0], ordered[1:]


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

def repair_tasks(
    tasks,
    *,
    live_task_ids: Iterable[str] = (),
    now: Optional[datetime] = None,
    host: Optional[str] = None,
    pid_alive: Optional[Callable[[int], bool]] = None,
    grace_seconds: int = ORPHAN_GRACE_SECONDS,
    now_iso: Optional[str] = None,
) -> tuple:
    """Return ``(repaired_tasks, repairs)`` for a queue in an impossible state.

    Pure: the input list and its dicts are never mutated. Each repair is a
    dict carrying its own ``kind`` so the caller can log every class of damage
    distinctly rather than as one anonymous "fixed the queue" line:

      - ``orphaned_running_requeued``   — ``running`` with no live owner → ``queued``
      - ``duplicate_seeded_task_merged``— two rows for one Supabase row → the one with progress
      - ``duplicate_id_reassigned``     — distinct work sharing an id → suffixed unique ids
      - ``duplicate_id_merged``         — indistinguishable rows sharing an id → the one with progress
      - ``stale_retry_window_cleared``  — terminal row holding ``retry_not_before``
      - ``unknown_status_requeued``     — unrecognised status → ``queued``
      - ``dropped_non_object``          — a list entry that is not a JSON object

    Deliberately NOT repaired here: a missing ``title``, or any other field
    that only cosmetically fails the schema. Those are reported by ``doctor``
    and filled in only under ``--fix``; inventing values on every load would
    rewrite the queue behind the operator's back.
    """
    if not isinstance(tasks, list):
        return [], [{
            "kind": "queue_not_a_list",
            "task_id": None,
            "detail": f"replaced a {type(tasks).__name__} with an empty queue",
        }]

    now = now or datetime.utcnow()
    now_iso = now_iso or now.isoformat()
    repairs: list[dict] = []

    working: list[dict] = []
    for index, task in enumerate(tasks):
        if isinstance(task, dict):
            working.append(dict(task))
            continue
        repairs.append({
            "kind": "dropped_non_object",
            "task_id": f"<index {index}>",
            "detail": f"dropped a {type(task).__name__} entry from the task list",
        })

    # 1. Two local rows for one Supabase mission_tasks row: a true duplicate.
    #    Collapse before touching ids — the seeded id is the stronger identity.
    survivors: list[dict] = []
    dropped: set = set()
    for seeded_id, rows in _group_by(working, "seeded_task_id").items():
        if len(rows) < 2:
            continue
        winner, losers = _dedupe_group(rows)
        for loser in losers:
            dropped.add(id(loser))
        repairs.append({
            "kind": "duplicate_seeded_task_merged",
            "task_id": winner.get("id"),
            "detail": (
                f"kept the row with the most progress (status "
                f"'{winner.get('status')}') for seeded_task_id {seeded_id}; "
                f"dropped {len(losers)} duplicate(s)"
            ),
            "seeded_task_id": seeded_id,
            "dropped_statuses": [l.get("status") for l in losers],
        })
    survivors = [t for t in working if id(t) not in dropped]

    # 2. Colliding local ids. Rows carrying *different* seeded_task_ids are
    #    genuinely different work that was seeded under the same id (the
    #    triple-seeded "AI Infra" mission), so they are re-identified, never
    #    dropped. Rows with nothing to tell them apart are true duplicates.
    deduped: list[dict] = []
    dropped = set()
    for id_value, rows in _group_by(survivors, "id").items():
        if len(rows) < 2:
            continue
        distinct_seeded = {r.get("seeded_task_id") for r in rows if r.get("seeded_task_id")}
        if len(distinct_seeded) == len(rows):
            ordered = sorted(rows, key=progress_score, reverse=True)
            for suffix, row in enumerate(ordered[1:], start=2):
                new_id = f"{id_value}-{suffix}"
                existing = {r.get("id") for r in survivors} | {r.get("id") for r in deduped}
                while new_id in existing:
                    suffix += 1
                    new_id = f"{id_value}-{suffix}"
                repairs.append({
                    "kind": "duplicate_id_reassigned",
                    "task_id": new_id,
                    "detail": (
                        f"'{id_value}' was shared by {len(rows)} rows with distinct "
                        f"seeded_task_ids; re-identified this one as '{new_id}' so "
                        "status writes are unambiguous"
                    ),
                    "previous_id": id_value,
                    "seeded_task_id": row.get("seeded_task_id"),
                })
                row["id"] = new_id
                row["updated_at"] = now_iso
                deduped.append(row)
            continue

        winner, losers = _dedupe_group(rows)
        for loser in losers:
            dropped.add(id(loser))
        repairs.append({
            "kind": "duplicate_id_merged",
            "task_id": id_value,
            "detail": (
                f"{len(rows)} indistinguishable rows shared id '{id_value}'; kept the "
                f"one with the most progress (status '{winner.get('status')}')"
            ),
            "dropped_statuses": [l.get("status") for l in losers],
        })
    survivors = [t for t in survivors if id(t) not in dropped]

    # 3. Per-record impossible states.
    for task in survivors:
        status = task.get("status")

        if isinstance(status, str) and status and status not in STATUSES:
            repairs.append({
                "kind": "unknown_status_requeued",
                "task_id": task.get("id"),
                "detail": f"status '{status}' is not a known status; requeued for a clean retry",
                "previous_status": status,
            })
            task["status"] = "queued"
            task["updated_at"] = now_iso
            status = "queued"
        elif not status:
            repairs.append({
                "kind": "unknown_status_requeued",
                "task_id": task.get("id"),
                "detail": "record carried no status; requeued for a clean retry",
                "previous_status": status,
            })
            task["status"] = "queued"
            task["updated_at"] = now_iso
            status = "queued"

        if status == "running":
            verdict = classify_running_task(
                task,
                live_task_ids=live_task_ids,
                now=now,
                host=host,
                pid_alive=pid_alive,
                grace_seconds=grace_seconds,
            )
            if not verdict["live"]:
                repairs.append({
                    "kind": "orphaned_running_requeued",
                    "task_id": task.get("id"),
                    "detail": (
                        f"'running' with no live session owner ({verdict['reason']}); "
                        "requeued so the loop can claim it again"
                    ),
                    "reason": verdict["reason"],
                    "last_updated_at": task.get("updated_at"),
                })
                task["status"] = "queued"
                task["updated_at"] = now_iso
                task.pop("owner_pid", None)
                task.pop("owner_host", None)
                status = "queued"

        if status in TERMINAL_STATUSES and task.get("retry_not_before"):
            repairs.append({
                "kind": "stale_retry_window_cleared",
                "task_id": task.get("id"),
                "detail": (
                    f"a '{status}' task held retry_not_before="
                    f"{task['retry_not_before']}; cleared as unreachable"
                ),
                "cleared_retry_not_before": task["retry_not_before"],
            })
            task.pop("retry_not_before", None)
            task["updated_at"] = now_iso

        # An owner record only means something while a task is running.
        if status != "running" and ("owner_pid" in task or "owner_host" in task):
            task.pop("owner_pid", None)
            task.pop("owner_host", None)

    return survivors, repairs


def apply_field_defaults(tasks: list, *, now_iso: str) -> tuple:
    """Fill in missing required fields. Only ever called by ``doctor --fix``.

    Kept out of ``repair_tasks`` on purpose: a placeholder title is a cosmetic
    guess, and guessing on every load would silently rewrite records the
    operator never asked us to touch.
    """
    repaired = [dict(t) for t in tasks if isinstance(t, dict)]
    fixes: list[dict] = []
    used_ids = {t.get("id") for t in repaired if isinstance(t.get("id"), str) and t.get("id")}

    for index, task in enumerate(repaired):
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            new_id = f"recovered-task-{index + 1}"
            suffix = index + 1
            while new_id in used_ids:
                suffix += 1
                new_id = f"recovered-task-{suffix}"
            used_ids.add(new_id)
            fixes.append({
                "kind": "missing_id_generated",
                "task_id": new_id,
                "detail": "record had no usable id; generated one so it can be tracked",
            })
            task["id"] = new_id
            task["updated_at"] = now_iso

        title = task.get("title")
        if not isinstance(title, str) or not title.strip():
            fixes.append({
                "kind": "missing_title_defaulted",
                "task_id": task.get("id"),
                "detail": "record had no title; defaulted to its id",
            })
            task["title"] = str(task.get("id"))
            task["updated_at"] = now_iso

        retry_count = task.get("retry_count")
        if isinstance(retry_count, int) and not isinstance(retry_count, bool) and retry_count < 0:
            fixes.append({
                "kind": "negative_retry_count_reset",
                "task_id": task.get("id"),
                "detail": f"retry_count was {retry_count}; reset to 0",
            })
            task["retry_count"] = 0
            task["updated_at"] = now_iso

    return repaired, fixes
