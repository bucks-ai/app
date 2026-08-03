# M4c.0 — Task state integrity

`.runtime/tasks.local.json` is the runner's only durable record of what it is
supposed to do, and until M4c.0 it was a bare JSON list with no schema, no
invariants, and no repair path. The founder hand-edited it at least five times
during M4b to recover from states the runner created and could not exit.

This document is the reference for the data layer that ended that: what a task
record *is*, which transitions are possible, what gets repaired automatically,
and where the line sits between this work and m4c-03.

## The states that forced hand edits

| Incident | Frequency in M4b | What the file looked like |
| --- | --- | --- |
| Stranded `running` | 4× (m4b-07/08/09/10) | An interrupted run left the in-flight task at `running` forever. Requeue logic only handled `blocked`, so the next loop saw zero `queued` work and exited `seeded_queue_exhausted` — looking finished while actually stalled. |
| Colliding ids | 3× | "Execute: AI Infra" was seeded three times: 15 tasks, ids `ai-infra-1..5` repeated three times. Status writes key off `id`, so a completion could land on the wrong row. Fixed by a hand-written `dedupe_ai_infra_tasks.py`. |
| Stale retry window | — | A finished task still holding `retry_not_before`, meaningless once terminal and misleading in every report that reads it. |
| Truncated queue | — | A `write_text` interrupted mid-save takes the whole queue with it: the file is opened for truncation before the first byte is written. |

## Schema

Defined in `tools/task_schema.py`. Pure — no clock, no filesystem, no process
inspection; the caller injects all three.

- **Required:** `id`, `title`, `status` (each non-empty).
- **Statuses:** `queued`, `running`, `complete`, `failed`, `blocked`.
  `blocked` is *not* terminal — it is a parked task awaiting a human action,
  which `requeue_fulfilled_blocked_tasks` returns to `queued`.
- **Terminal:** `complete`, `failed`.
- **Typed fields:** see `FIELD_TYPES`. Unknown extra keys are allowed on
  purpose — tools attach their own metadata (`completion_evidence`, `dry_run`,
  `dedupe_note`) and the schema must not fight them. Only a *known* field with
  the wrong type is a violation.
- **Cross-record:** ids are globally unique; one Supabase `mission_tasks` row
  maps to at most one local record.

### Transitions

```
queued   → queued, running, blocked, failed, complete
running  → running, queued, blocked, failed, complete
blocked  → blocked, queued, running, failed, complete
failed   → failed, queued, blocked
complete → complete, queued
```

Permissive about forward motion, strict about leaving a terminal state: the
only way out of `complete`/`failed` is an explicit requeue. A rejected write is
logged as `task_transition_rejected` and skipped, so a late or duplicated write
cannot re-open a task the runner already finished. An *unknown* source status
is permissive — that record is already broken, and repair rather than rejection
is the answer for it.

## Session ownership

`mark_task_running` stamps `owner_pid` and `owner_host`. That turns "is this
`running` task actually running?" from a guess into a kernel question
(`os.kill(pid, 0)`).

Resolution order, in `classify_running_task`:

1. The current session names the id in `.runtime/state.local.json` → **live**.
2. The row names an owner process on *this* host → alive means **live**, gone
   means **orphaned**. Every row written after M4c.0 lands here.
3. The row names an owner on another host → unverifiable → **live**.
4. No owner record (a row predating M4c.0) → **orphaned** only once untouched
   for `ORPHAN_GRACE_SECONDS` (1 hour, comfortably above the 41.1-minute
   longest task observed in the M4c.0 calibration data). With no timestamp
   either, there is nothing to measure and it stays **live**.

Every ambiguous case resolves to live. Requeueing a task a healthy loop is
still executing runs the same work twice — worse than leaving one stranded row
for `doctor` to surface, which is why cases 3 and 4-without-timestamp are
reported instead of repaired.

## Auto-repair on load

`load_tasks()` repairs, persists atomically, and logs each class of damage as
its own `task_queue_repaired` event (plus one `task_queue_repair_summary`).
Pass `repair=False` to see the file as it actually is — `doctor` does this so
it reports the damage rather than a queue it has already quietly fixed.

| Repair kind | Trigger | Action |
| --- | --- | --- |
| `orphaned_running_requeued` | `running`, no live owner | → `queued`, owner record cleared |
| `duplicate_seeded_task_merged` | two rows, one `seeded_task_id` | keep the row with real progress |
| `duplicate_id_reassigned` | one id, distinct `seeded_task_id`s | re-identify as `<id>-2`, `<id>-3`, … |
| `duplicate_id_merged` | one id, nothing to tell the rows apart | keep the row with real progress |
| `stale_retry_window_cleared` | terminal row holds `retry_not_before` | drop the field |
| `unknown_status_requeued` | status absent or unrecognised | → `queued` |
| `dropped_non_object` | a list entry that is not an object | drop it |

Two deliberate non-behaviours:

- **Distinct work is never dropped.** Triple-seeded rows share an id but carry
  *different* `seeded_task_id`s, so they are three real mission tasks. They get
  unique ids; collapsing them by title (what the one-off script did) is
  mission-specific policy, not a data-layer rule.
- **Cosmetic defects are not repaired on load.** A missing `title` is reported,
  not invented. Filling fields on every load would rewrite records behind the
  operator's back; `doctor --fix` does it on request
  (`apply_field_defaults`).

"Real progress" ranks `complete` > `failed` > `blocked` > `running` > `queued`,
then hard evidence of work (a summary, completion evidence, a retry history),
then recency. Losing a `complete` row would re-run finished work — the most
expensive mistake available here — so it outranks everything.

## Atomic writes

Every save is a sibling temp file, `flush` + `fsync`, then `os.replace` — an
atomic rename within the same filesystem. An interrupted process leaves either
the previous queue or the new one, never a half-written list. A queue that is
unreadable JSON is copied to `tasks.local.json.corrupt.<timestamp>` before
being reset, so nothing is silently discarded.

The test suite is blocked from writing the real queue (`_persist_queue`): once
loads started repairing, a test that forgot to redirect `_tasks_path` would
rewrite live runtime state. Same reasoning and same mechanism as the Slack
fan-out guard in `log_tools`.

## `python main.py doctor`

```bash
python main.py doctor                # report only; exits 1 when unhealthy
python main.py doctor --fix          # apply the repairs
python main.py doctor --json         # machine-readable report
python main.py doctor --no-supabase  # skip the mission_tasks divergence check
```

Reports counts by status, orphans (with the reason each was judged orphaned),
`running` rows that could not be verified either way, duplicates, every schema
and invariant violation, and — for seeded missions — divergence from the
Supabase `mission_tasks` rows:

- `status_mismatch` — both sides exist and disagree (when the local side is
  terminal, the sync-back did not land)
- `missing_in_supabase` — a local row points at a `mission_tasks` row that no
  longer exists
- `missing_locally` — Supabase has a task for a mission in play that the local
  queue never seeded

Divergence is **reported, never resolved**. `doctor` writes nothing to
Supabase: a diagnostic command should not be silently authoritative over the
database. Reconciliation is m4c-03's.

## Boundary with m4c-03

m4c-03 ("State self-healing") covers the same three failure modes at the graph
level. This task built the substrate underneath it; the split is *structure vs
policy*:

| This task (data layer) | m4c-03 (graph layer) |
| --- | --- |
| What a valid task record is; enforcement on load and save | When to run reconciliation in the loop lifecycle |
| Whether a `running` row has a live owner, and requeueing it when it does not | Startup orchestration of that requeue, and what the loop does next |
| Globally-unique ids; duplicate rows collapsed or re-identified | Idempotent *seeding* — not creating the duplicates in the first place; Supabase as source of truth |
| Reporting local↔Supabase divergence | Resolving it |
| `retry_not_before` is structurally invalid on a terminal task | Classifying an error as transient vs genuine, so it never becomes terminal wrongly |
| — | Pruning mission-specific placeholder tasks (e.g. `rls-fixture-task`) |

Nothing here imports from `graph.py`, and no graph node was changed. m4c-03
gets its startup requeue for free through `load_tasks()` and can call
`repair_tasks`, `validate_tasks`, and `diff_against_mission_tasks` directly for
anything more deliberate.

## Tests

- `tests/test_task_schema.py` — validation, transitions, orphan classification,
  every repair, idempotency (repairing twice is a no-op, and repaired output is
  schema-valid).
- `tests/test_queue_doctor.py` — report contents, Supabase divergence,
  formatting, `run_doctor` with and without `--fix`.
- `tests/test_task_queue_integrity.py` — atomic saves (including a save
  interrupted mid-`os.replace`), auto-repair on load, ownership stamping,
  transition enforcement, and the live-state write guard.
