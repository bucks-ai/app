"""Graph-level state self-healing (m4c-03) — policy over M4c.0's structure.

``tools/task_schema.py`` answers *what a valid task record is* and *how a
broken file is made valid again*. This module answers the three questions that
only make sense with the loop lifecycle in view, each one a state the founder
fixed by hand-editing ``.runtime/tasks.local.json`` during M4b:

1. **Startup orchestration of the orphan requeue.** ``load_tasks`` already
   repairs an orphaned ``running`` row on the way through, silently, as a side
   effect of whichever caller happened to read the queue first. ``run_startup_heal``
   makes that a deliberate, reported pass before the first task is claimed —
   and adds the part a data layer cannot decide: a task that is orphaned again
   on every restart is a crash loop, not a flake, so after
   ``MAX_ORPHAN_REQUEUES`` it is parked ``blocked`` for a human instead of
   being fed back into the same crash. It also prunes mission-specific
   placeholder rows (``rls-fixture-task``), which are policy, not schema.

2. **Idempotent seeding.** "Execute: AI Infra" was seeded three times because
   nothing asked whether the mission was already in the local queue: 15 rows,
   ids ``ai-infra-1..5`` repeated three times, status writes landing on
   whichever row matched first. ``plan_mission_seeding`` treats the Supabase
   ``mission_tasks`` rows as the source of truth and returns only what is
   genuinely missing locally, with ids made globally unique before they are
   written rather than de-duplicated afterwards.

3. **Transient vs genuine failure.** A degraded network broke a Supabase
   lookup, the task was marked ``failed`` with "business not found", and
   because ``failed`` is terminal every relaunch exhausted the queue in 30s
   until the file was hand-edited. ``classify_error`` separates *the
   infrastructure was unreachable* from *the work itself is wrong*. A
   transient failure is *never* terminal: it retries with backoff and, once
   the retries are spent, parks as ``blocked`` — a state a human (or a
   fulfillment file) can lift, unlike ``failed``.

Everything here is pure except ``run_startup_heal`` and
``call_with_transient_retry``'s injected callable: the clock, the host,
process liveness and the queue itself are all supplied by the caller.
"""
from __future__ import annotations

import re
import socket
import time
from datetime import datetime
from typing import Callable, Iterable, Optional

from tools.task_schema import (
    ORPHAN_GRACE_SECONDS,
    TERMINAL_STATUSES,
    classify_running_tasks,
    repair_tasks,
)

# ---------------------------------------------------------------------------
# 1. Startup self-heal
# ---------------------------------------------------------------------------

#: How many restarts in a row may requeue the same orphaned ``running`` task
#: before it is parked for a human. An interrupted run is normal and requeueing
#: is exactly right; the *same* task stranded on every restart means the work
#: itself kills the process, and requeueing it again just burns the next run.
#: Not an env var on purpose — this is a correctness backstop, not a tuning
#: knob, and any value above ~3 stops being a backstop at all.
MAX_ORPHAN_REQUEUES = 3

#: Rows created by test fixtures that seeded a real Supabase mission and left
#: their task behind in the local queue. Matched by exact id: a substring rule
#: would eventually eat a real task whose id happens to contain "fixture".
PLACEHOLDER_TASK_IDS = frozenset({"rls-fixture-task"})


def has_real_work(task: dict) -> bool:
    """True when a row carries evidence that a worker actually ran for it.

    The one thing pruning must never do is discard a record of work that
    happened. A summary, completion evidence, a commit, a recorded error or an
    in-flight status all count; a bare row that only ever existed does not.
    """
    if not isinstance(task, dict):
        return False
    if task.get("status") == "running":
        return True
    return any(
        task.get(field)
        for field in ("summary", "completion_evidence", "error", "last_commit", "pr_number")
    )


def is_placeholder_task(task: dict) -> bool:
    """True when *task* is a known fixture leftover with nothing to preserve."""
    if not isinstance(task, dict):
        return False
    return task.get("id") in PLACEHOLDER_TASK_IDS and not has_real_work(task)


def plan_startup_heal(
    tasks,
    *,
    live_task_ids: Iterable[str] = (),
    now: Optional[datetime] = None,
    host: Optional[str] = None,
    pid_alive: Optional[Callable[[int], bool]] = None,
    grace_seconds: int = ORPHAN_GRACE_SECONDS,
    now_iso: Optional[str] = None,
    max_orphan_requeues: int = MAX_ORPHAN_REQUEUES,
) -> dict:
    """Return the whole startup heal as data, without touching the queue.

    Runs M4c.0's ``repair_tasks`` first (orphans, duplicates, stale retry
    windows), then applies the two policy decisions that sit above it:

    - **Placeholder pruning** — fixture rows with no evidence of work.
    - **Orphan requeue accounting** — each requeue bumps ``orphan_requeue_count``
      on the task; past ``max_orphan_requeues`` the task is parked ``blocked``
      rather than handed back to a loop that has already died on it that many
      times. ``blocked`` and not ``failed``: the task is fine, the run wasn't.

    Returns ``{"tasks", "repairs", "pruned", "orphans_requeued", "parked_orphans",
    "unverifiable_running", "changed"}``.
    """
    now = now or datetime.utcnow()
    now_iso = now_iso or now.isoformat()

    original = tasks if isinstance(tasks, list) else []
    unverifiable = classify_running_tasks(
        original,
        live_task_ids=live_task_ids,
        now=now,
        host=host,
        pid_alive=pid_alive,
        grace_seconds=grace_seconds,
    )["unverifiable"]

    healed, repairs = repair_tasks(
        original,
        live_task_ids=live_task_ids,
        now=now,
        host=host,
        pid_alive=pid_alive,
        grace_seconds=grace_seconds,
        now_iso=now_iso,
    )

    kept: list[dict] = []
    pruned: list[dict] = []
    for task in healed:
        if is_placeholder_task(task):
            pruned.append({
                "task_id": task.get("id"),
                "status": task.get("status"),
                "detail": (
                    f"'{task.get('id')}' is a known fixture placeholder carrying no "
                    "summary, evidence or error; removed from the queue"
                ),
            })
            continue
        kept.append(task)

    orphan_ids = {
        repair.get("task_id")
        for repair in repairs
        if repair.get("kind") == "orphaned_running_requeued"
    }
    orphans_requeued: list[dict] = []
    parked: list[dict] = []
    for task in kept:
        if task.get("id") not in orphan_ids:
            continue
        count = task.get("orphan_requeue_count")
        count = (count if isinstance(count, int) and not isinstance(count, bool) else 0) + 1
        task["orphan_requeue_count"] = count
        task["updated_at"] = now_iso
        entry = {
            "task_id": task.get("id"),
            "orphan_requeue_count": count,
            "max_orphan_requeues": max_orphan_requeues,
        }
        if max_orphan_requeues > 0 and count > max_orphan_requeues:
            task["status"] = "blocked"
            task["error"] = (
                f"stranded 'running' and requeued {count} times across restarts "
                f"(limit {max_orphan_requeues}); parked for review rather than "
                "restarted into the same crash"
            )
            task.pop("owner_pid", None)
            task.pop("owner_host", None)
            parked.append({**entry, "detail": task["error"]})
        else:
            orphans_requeued.append(entry)

    return {
        "tasks": kept,
        "repairs": repairs,
        "pruned": pruned,
        "orphans_requeued": orphans_requeued,
        "parked_orphans": parked,
        "unverifiable_running": unverifiable,
        "changed": bool(repairs or pruned or orphans_requeued or parked),
    }


def summarize_startup_heal(plan: dict, *, task_count_before: int) -> dict:
    """Condense a heal plan into the payload logged and carried on state."""
    repairs = plan.get("repairs") or []
    kinds: dict[str, int] = {}
    for repair in repairs:
        kind = repair.get("kind", "unknown")
        kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "task_count_before": task_count_before,
        "task_count_after": len(plan.get("tasks") or []),
        "repairs_by_kind": dict(sorted(kinds.items())),
        "orphans_requeued": [o["task_id"] for o in plan.get("orphans_requeued") or []],
        "parked_orphans": [o["task_id"] for o in plan.get("parked_orphans") or []],
        "pruned": [p["task_id"] for p in plan.get("pruned") or []],
        "unverifiable_running": [u["task_id"] for u in plan.get("unverifiable_running") or []],
        "healed": bool(plan.get("changed")),
    }


def run_startup_heal() -> dict:
    """Heal the real queue once, before the first task of a run is claimed.

    Reads with ``repair=False`` so the pass sees the file as it actually is,
    applies ``plan_startup_heal``, persists atomically, and logs one
    ``startup_self_heal`` event carrying every class of damage it found — the
    founder should learn a run started stranded from the log, not by noticing
    it exited ``seeded_queue_exhausted`` in 30 seconds.

    Returns the summary dict (also suitable for ``RunnerState``).
    """
    from tools.log_tools import log_event
    from tools.task_tools import (
        _now,
        _persist_queue,
        _pid_alive,
        live_task_ids,
        load_tasks,
    )

    tasks = load_tasks(repair=False)
    if not isinstance(tasks, list):
        tasks = []

    plan = plan_startup_heal(
        tasks,
        live_task_ids=live_task_ids(),
        host=socket.gethostname(),
        pid_alive=_pid_alive,
        now_iso=_now(),
    )
    if plan["changed"]:
        _persist_queue(plan["tasks"])

    summary = summarize_startup_heal(plan, task_count_before=len(tasks))

    for orphan in plan["orphans_requeued"]:
        log_event("orphaned_task_requeued", {
            **orphan,
            "detail": "'running' with no live session owner; requeued at startup",
        }, orphan["task_id"])
    for orphan in plan["parked_orphans"]:
        log_event("orphaned_task_parked", orphan, orphan["task_id"])
    for entry in plan["pruned"]:
        log_event("placeholder_task_pruned", entry, entry["task_id"])

    log_event("startup_self_heal", summary)
    return summary


# ---------------------------------------------------------------------------
# 2. Idempotent seeding
# ---------------------------------------------------------------------------

def unique_task_id(candidate_id: str, taken: Iterable[str]) -> str:
    """Return ``candidate_id`` or the first free ``<id>-2``, ``<id>-3``, … .

    Same suffix scheme M4c.0's ``duplicate_id_reassigned`` repair uses, so a
    queue healed after the fact and a queue seeded correctly in the first place
    read identically.
    """
    taken = set(taken)
    if candidate_id not in taken:
        return candidate_id
    suffix = 2
    while f"{candidate_id}-{suffix}" in taken:
        suffix += 1
    return f"{candidate_id}-{suffix}"


def plan_mission_seeding(
    mission_id: str,
    candidates: list[dict],
    existing_tasks: list[dict],
    remote_rows: Optional[list[dict]] = None,
) -> dict:
    """Decide what of *candidates* may be added to a queue holding *existing_tasks*.

    Pure. ``candidates`` is the output of
    ``seeded_mission_queue.seed_tasks_from_mission``; ``remote_rows`` is the raw
    ``mission_tasks`` result, the source of truth for what the mission contains.

    Identity is the Supabase ``mission_tasks`` row id, never the local id:
    seeding derives local ids from the mission name and position, so the third
    seeding of one mission produces exactly the ids of the first. Returns:

      - ``to_add``       — task dicts, ids already made globally unique
      - ``skipped``      — ``{"task_id", "seeded_task_id", "existing_status"}``
                           per candidate already present locally
      - ``reassignments``— ``{"seeded_task_id", "requested_id", "assigned_id"}``
      - ``stale_local``  — local rows for this mission with no ``mission_tasks``
                           row behind them any more; ``prunable`` is False for a
                           row that reached a terminal state, which is history
                           and is kept
      - ``already_seeded``— the mission already has local rows
      - ``claim``        — whether the mission should still be marked ``running``
                           in Supabase (yes even when nothing new was added, or
                           the same queued mission is re-fetched forever)
    """
    mission_id = str(mission_id or "")
    existing_tasks = [t for t in (existing_tasks or []) if isinstance(t, dict)]
    candidates = [t for t in (candidates or []) if isinstance(t, dict)]

    existing_by_seeded_id = {
        str(t["seeded_task_id"]): t for t in existing_tasks if t.get("seeded_task_id")
    }
    taken_ids = {str(t["id"]) for t in existing_tasks if t.get("id")}

    to_add: list[dict] = []
    skipped: list[dict] = []
    reassignments: list[dict] = []

    for candidate in candidates:
        seeded_task_id = str(candidate.get("seeded_task_id") or "")
        existing = existing_by_seeded_id.get(seeded_task_id) if seeded_task_id else None
        if existing is not None:
            skipped.append({
                "task_id": existing.get("id"),
                "seeded_task_id": seeded_task_id,
                "existing_status": existing.get("status"),
            })
            continue

        task = dict(candidate)
        requested_id = str(task.get("id") or seeded_task_id or "seeded-task")
        assigned_id = unique_task_id(requested_id, taken_ids)
        if assigned_id != requested_id:
            reassignments.append({
                "seeded_task_id": seeded_task_id,
                "requested_id": requested_id,
                "assigned_id": assigned_id,
            })
        task["id"] = assigned_id
        taken_ids.add(assigned_id)
        if seeded_task_id:
            existing_by_seeded_id[seeded_task_id] = task
        to_add.append(task)

    mission_local = [
        t for t in existing_tasks if str(t.get("seeded_mission_id") or "") == mission_id
    ]
    stale_local: list[dict] = []
    if remote_rows is not None:
        remote_ids = {str(row.get("id")) for row in remote_rows if row.get("id") is not None}
        for task in mission_local:
            seeded_task_id = str(task.get("seeded_task_id") or "")
            if seeded_task_id and seeded_task_id not in remote_ids:
                stale_local.append({
                    "task_id": task.get("id"),
                    "seeded_task_id": seeded_task_id,
                    "status": task.get("status"),
                    "prunable": task.get("status") not in TERMINAL_STATUSES,
                })

    return {
        "to_add": to_add,
        "skipped": skipped,
        "reassignments": reassignments,
        "stale_local": stale_local,
        "already_seeded": bool(mission_local),
        "claim": True,
    }


# ---------------------------------------------------------------------------
# 3. Transient vs genuine errors
# ---------------------------------------------------------------------------

#: Phrases that mean "we could not reach the thing", grouped by the signal
#: reported alongside the verdict. Matched case-insensitively as substrings of
#: the error text.
#:
#: Deliberately absent: a bare "timed out"/"timeout". A worker CLI that runs
#: past CLAUDE_CLI_TIMEOUT_S says "timed out" too, and that is a local
#: degradation with its own guard (``worker_timeout_guard``) and its own
#: backoff (``is_degraded_failure``) — reclassifying it as transient here would
#: make a worker that never finishes un-failable. Only network-shaped timeout
#: phrasing counts.
_TRANSIENT_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dns", (
        "name or service not known",
        "temporary failure in name resolution",
        "nodename nor servname",
        "getaddrinfo failed",
        "name resolution",
        "dns lookup",
        "could not resolve host",
    )),
    ("connection", (
        "connection reset",
        "connection refused",
        "connection aborted",
        "connection error",
        "connection closed",
        "broken pipe",
        "network is unreachable",
        "network unreachable",
        "no route to host",
        "remote end closed connection",
        "server disconnected",
        "max retries exceeded",
        "eof occurred in violation of protocol",
        "ssl handshake",
        "sslerror",
        "protocol error",
    )),
    ("timeout", (
        "connection timed out",
        "connect timeout",
        "read timeout",
        "request timed out",
        "operation timed out",
        "etimedout",
        "deadline exceeded",
        "gateway timeout",
    )),
    ("rate_limit", (
        "rate limit",
        "rate-limited",
        "too many requests",
        "slow down",
    )),
    ("server_error", (
        "internal server error",
        "bad gateway",
        "service unavailable",
        "server overloaded",
        "upstream connect error",
        "temporarily unavailable",
    )),
)

#: HTTP status codes that mean "try again": 429 and every 5xx. Anchored to a
#: status-ish prefix so a commit sha, a byte count or a port number containing
#: "503" is not read as a server error.
_STATUS_CODE_PATTERN = re.compile(
    r"(?:http(?:\s+error)?|status(?:\s+code)?|code|error|response)\s*[:=]?\s*(429|5\d{2})\b",
    re.IGNORECASE,
)

#: Exception *class names* that are transient whatever their message says.
#: Matched by name so this module never imports requests/httpx/urllib3 just to
#: classify a string.
_TRANSIENT_EXCEPTION_NAMES = frozenset({
    "ConnectionError",
    "ConnectionResetError",
    "ConnectionAbortedError",
    "ConnectionRefusedError",
    "Timeout",
    # socket.timeout is an alias of TimeoutError from Python 3.10. A worker CLI
    # that overruns raises subprocess.TimeoutExpired, which is deliberately not
    # on this list — see _TRANSIENT_MARKERS.
    "TimeoutError",
    "ConnectTimeout",
    "ReadTimeout",
    "ConnectTimeoutError",
    "ReadTimeoutError",
    "ProtocolError",
    "URLError",
    "RemoteDisconnected",
    "IncompleteRead",
    "gaierror",
    "herror",
    "timeout",
    "socket.timeout",
    "NewConnectionError",
    "MaxRetryError",
    "ServerDisconnectedError",
    "APIConnectionError",
    "APITimeoutError",
    "RateLimitError",
    "InternalServerError",
    "ServiceUnavailableError",
})

GENUINE = "genuine"
TRANSIENT = "transient"


def classify_error(error) -> dict:
    """Classify *error* (an exception or a message) as transient or genuine.

    Returns ``{"class": "transient"|"genuine", "signal": str|None, "detail": str}``.

    **Transient** means the infrastructure was unreachable or busy — DNS,
    connection, network timeout, rate limit, 5xx. The work was never attempted,
    so nothing about it has been proven wrong and it must never end up in a
    terminal state.

    **Genuine** is everything else, including anything unrecognised: the
    default has to be the conservative one, because wrongly calling a real
    failure transient retries broken work forever, and that is a worse failure
    than the one this module exists to fix.
    """
    if error is None:
        return {"class": GENUINE, "signal": None, "detail": "no error text"}

    if isinstance(error, BaseException):
        chain: list[BaseException] = []
        cursor: Optional[BaseException] = error
        seen: set[int] = set()
        while cursor is not None and id(cursor) not in seen and len(chain) < 10:
            seen.add(id(cursor))
            chain.append(cursor)
            cursor = cursor.__cause__ or cursor.__context__
        for exc in chain:
            name = type(exc).__name__
            if name in _TRANSIENT_EXCEPTION_NAMES:
                return {
                    "class": TRANSIENT,
                    "signal": "exception_type",
                    "detail": f"{name} is a transport-level failure",
                }
        text = " ".join(f"{type(e).__name__}: {e}" for e in chain)
    else:
        text = str(error)

    lowered = text.lower()
    for signal, markers in _TRANSIENT_MARKERS:
        for marker in markers:
            if marker in lowered:
                return {
                    "class": TRANSIENT,
                    "signal": signal,
                    "detail": f"matched transient marker '{marker}'",
                }

    match = _STATUS_CODE_PATTERN.search(text)
    if match:
        return {
            "class": TRANSIENT,
            "signal": "rate_limit" if match.group(1) == "429" else "server_error",
            "detail": f"HTTP {match.group(1)} is retryable",
        }

    return {"class": GENUINE, "signal": None, "detail": "no transient signal found"}


def is_transient_error(error) -> bool:
    """True when ``classify_error`` calls *error* transient."""
    return classify_error(error)["class"] == TRANSIENT


def transient_retry_count(task: Optional[dict]) -> int:
    """How many times this task has already been retried for a transient error."""
    if not isinstance(task, dict):
        return 0
    try:
        return max(0, int(task.get("transient_retry_count", 0) or 0))
    except (TypeError, ValueError):
        return 0


def decide_failure_disposition(
    error,
    task: Optional[dict] = None,
    *,
    max_transient_retries: int = 5,
) -> dict:
    """Decide what a just-failed task's *error* permits doing to the task.

    Returns ``{"error_class", "signal", "action", "terminal_allowed",
    "transient_retry_count", "detail"}`` where ``action`` is one of:

      - ``"retry"``  — transient, retries remain: requeue with backoff.
      - ``"park"``   — transient, retries spent: ``blocked``, never ``failed``.
                       A human (or a fulfillment file) can lift ``blocked``;
                       nothing lifts ``failed`` without editing the queue by
                       hand, which is the incident this exists to prevent.
      - ``"defer"``  — genuine: the existing failure guard owns the decision,
                       including marking the task terminal once its retries are
                       exhausted.
    """
    verdict = classify_error(error)
    prior = transient_retry_count(task)

    if verdict["class"] != TRANSIENT:
        return {
            "error_class": GENUINE,
            "signal": None,
            "action": "defer",
            "terminal_allowed": True,
            "transient_retry_count": prior,
            "detail": verdict["detail"],
        }

    if max_transient_retries > 0 and prior < max_transient_retries:
        return {
            "error_class": TRANSIENT,
            "signal": verdict["signal"],
            "action": "retry",
            "terminal_allowed": False,
            "transient_retry_count": prior + 1,
            "detail": verdict["detail"],
        }

    return {
        "error_class": TRANSIENT,
        "signal": verdict["signal"],
        "action": "park",
        "terminal_allowed": False,
        "transient_retry_count": prior,
        "detail": (
            f"{verdict['detail']}; {prior} transient retries already spent "
            f"(limit {max_transient_retries})"
        ),
    }


def call_with_transient_retry(
    fn: Callable,
    *,
    op: str,
    attempts: int = 3,
    base_delay_s: float = 2.0,
    _sleep: Callable[[float], None] = time.sleep,
    **payload,
) -> dict:
    """Call *fn* with linear backoff, retrying only genuinely transient errors.

    The generalisation of the 2026-07-31 mitigation in ``fetch_business_by_id``
    (3 attempts, 2s/4s linear backoff, a distinct unreachable event). Every
    Supabase/HTTP lookup whose failure would otherwise be indistinguishable
    from "the row does not exist" should route through this.

    Returns ``{"ok", "value", "error", "transient", "signal", "attempts"}``.
    A non-transient exception returns immediately — retrying work that is
    genuinely wrong just spends the clock.
    """
    from tools.log_tools import log_event

    for attempt in range(1, max(1, attempts) + 1):
        try:
            return {
                "ok": True,
                "value": fn(),
                "error": None,
                "transient": False,
                "signal": None,
                "attempts": attempt,
            }
        except Exception as exc:  # noqa: BLE001 - classification is the point
            verdict = classify_error(exc)
            transient = verdict["class"] == TRANSIENT
            will_retry = transient and attempt < max(1, attempts)
            log_event("transient_retry" if transient else "operation_failed", {
                "op": op,
                "attempt": attempt,
                "attempts": attempts,
                "error_class": verdict["class"],
                "signal": verdict["signal"],
                "error": str(exc),
                "will_retry": will_retry,
                **payload,
            })
            if not will_retry:
                return {
                    "ok": False,
                    "value": None,
                    "error": str(exc),
                    "transient": transient,
                    "signal": verdict["signal"],
                    "attempts": attempt,
                }
            _sleep(base_delay_s * attempt)

    # Unreachable: the loop either returns a value or a failure dict.
    return {
        "ok": False, "value": None, "error": "no attempts made",
        "transient": False, "signal": None, "attempts": 0,
    }
