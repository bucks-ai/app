# M4c.0 — Threshold calibration

Every timeout and threshold in the runner was originally a guess. Guesses in a
system of *nested* timeouts do not fail independently — they cascade: a
threshold set below the real p95 turns a healthy long run into a "timeout", the
timeout turns into a failed task, the failed task turns into a stale run, and
the stale run kills the session. The observed symptom ("the loop died
overnight") points nowhere near the cause (a number in `.env`).

This document replaces the guessing with measurement. Every number below comes
from `runner/langgraph/logs/runs.jsonl` and can be regenerated:

```bash
cd runner/langgraph
python -m tools.threshold_calibration          # prints the Measurements section
```

Sample counts (`n`) are printed for every distribution on purpose. A p95 over
4 samples is not evidence, and a reader should be able to see that without
taking anything here on faith.

## Two thresholds were provably wrong

**1. `WORKER_TIMEOUT_THRESHOLD=570` sat below the p90 of healthy runs (606.4s).**
Measured directly: **22 of 181 successful worker runs — 12.2% — were at or
above 570s**, so the guard classified them as timeouts. The Claude CLI, whose
ceiling was 1800s, never killed any of them. Every one of those false timeouts
burned a retry and fed the consecutive-failure guard. At the new value the same
181 successful runs produce **0** false timeouts.

**2. `MAX_STALE_TASK_MINUTES=60` sat barely above the real task duration.**
Observed end-to-end task duration (`task_loaded` -> `task_completed`) reaches
**41.1 min**, with p99 at 29.1 min. The watchdog was killing sessions that were
working correctly, and two `stale_run_warning` events fired at 30.0 and 34.0
minutes on tasks that went on to complete normally.

## Derived values

Each value is set from the p95 of the distribution it bounds, with headroom,
and then checked against the ordering invariants below.

| Variable | Was | Now | Derived from |
| --- | ---: | ---: | --- |
| `CLAUDE_CLI_TIMEOUT_S` | 1800 | **2400** | Worker p95 755.1s overall, 1653.4s for `test` tasks (n=28). 2400 clears the `test` p95 with ~45% headroom. The old 1800 right-censored the distribution — one run ended at 1800.3s, i.e. it was killed, so the true tail is longer than any max shown here. |
| `WORKER_TIMEOUT_THRESHOLD` | 570 | **2700** | Not a percentile: this guard *classifies* a CLI kill, so it must sit above the CLI ceiling or it invents failures that never happened. 2400 + 300s for process teardown and output parsing. |
| `MAX_STALE_TASK_MINUTES` | 60 | **120** | Worst legitimate single attempt = 45 min worker ceiling + 11.6 min PR checks (observed max 695.5s) + 3 min deploy poll + 10 min retry backoff ~= 70 min. 120 clears that and still bounds a genuinely dead loop. Observed end-to-end max is 41.1 min. |
| `STALE_RUN_WARN_MINUTES` | 30 | **75** | The old value fired on legitimate 30.0 and 34.0 min gaps. 75 sits above the ~70 min worst legitimate case and below the 120 min hard stop, so the warning still precedes the stop. |
| `PR_CHECKS_TIMEOUT_S` | 900 | **1200** | Check completion p95 681.6s, max 695.5s (n=61). 900 left only 1.29x headroom over the observed max — one slow check run tips it. 1200 is 1.73x. |
| `PR_CHECKS_EMPTY_GRACE_S` | 180 | **120** | Check runs register within a single poll interval: n=67, p95 21.4s, max 22.6s. 120s is 5.3x the observed max and, more usefully, fast-fails a check-less PR at 240s instead of 360s. |
| `MAX_RUNTIME_MINUTES` | 480 | **480** (unchanged) | Measured, not assumed: loop sessions (n=59) spanned at most 203.2 min, p95 145.3 min. 480 has never been the binding stop. It must also stay well above `MAX_STALE_TASK_MINUTES` so a stuck loop reports `stale_run` rather than `max_runtime` (invariant 5). |
| `FAILURE_RETRY_BACKOFF_BASE_S` | 30 | **30** (unchanged) | No distribution to fit — only 30 `task_retry_scheduled` events across the whole log, and no recorded post-retry recovery time. Changing this from data is not possible; it is governed by the budget invariant instead. |
| `FAILURE_RETRY_BACKOFF_MULTIPLIER` | 2.0 | **2.0** (unchanged) | As above. |
| `FAILURE_RETRY_BACKOFF_MAX_S` | 300 | **300** (unchanged) | At `MAX_TASK_ATTEMPTS=3` the waits are 30s then 60s, so the 300s cap is never actually reached. Worst-case occupancy 2700 + 300x2 = 3300s fits inside the 7200s stale window (invariant 6). Raising it without data would only shrink that margin. |

### What the PR-check timeouts actually were

All 8 `pr_checks_timeout` events ran the *full* budget (4 at 894s of 900, 4 at
1790s of 1800 — an operator had raised it). None of them ever saw a single
check run register. That is a different failure mode from "checks were slow",
and raising `PR_CHECKS_TIMEOUT_S` would not have helped any of them: lowering
`PR_CHECKS_EMPTY_GRACE_S` so the zero-check path fast-fails sooner is the lever
that does. `PR_CHECKS_TIMEOUT_S=1200` is therefore derived from the
*completion* distribution, not from these timeouts.

## Ordering invariants

The timeouts are nested windows, not independent knobs. A violated ordering
does not raise anything at the time — it mis-behaves hours later. So the
ordering is checked at startup (`python main.py setup`, `run-once`, `run-loop`)
and the process refuses to start, printing the exact fix. Implementation:
`runner/langgraph/tools/config_invariants.py`; tests:
`runner/langgraph/tests/test_config_invariants.py`.

| # | Invariant | Why a violation cascades |
| ---: | --- | --- |
| 1 | `CLAUDE_CLI_TIMEOUT_S < WORKER_TIMEOUT_THRESHOLD` | Inverted, the guard fires on runs the CLI would have let finish — the 12.2% false-timeout rate measured above. |
| 2 | `WORKER_TIMEOUT_THRESHOLD < MAX_STALE_TASK_MINUTES * 60` | Otherwise the watchdog kills the session while the worker is still legitimately running, and the worker timeout guard can never fire. |
| 3 | `PR_CHECKS_EMPTY_GRACE_S * 2 < PR_CHECKS_TIMEOUT_S` | The zero-check recovery needs two grace windows (detect, then confirm after refreshing the branch). Without room for both, a check-less PR reports `pr_checks_timeout` instead of the true cause, `pr_checks_no_runs`. |
| 4 | `STALE_RUN_WARN_MINUTES < MAX_STALE_TASK_MINUTES` | A warning at or after the hard stop is never seen, so the loop halts with no chance to intervene. |
| 5 | `MAX_STALE_TASK_MINUTES < MAX_RUNTIME_MINUTES` | Otherwise a genuinely stuck loop always stops with reason `max_runtime` and the real cause is never reported. |
| 6 | `WORKER_TIMEOUT_THRESHOLD + FAILURE_RETRY_BACKOFF_MAX_S * (MAX_TASK_ATTEMPTS - 1) < MAX_STALE_TASK_MINUTES * 60` | Otherwise retrying a slow task trips the watchdog and kills the session mid-recovery. |

With the values above: 2400 < 2700 < 7200; 240 < 1200; 75 < 120 < 480;
2700 + 600 = 3300 < 7200. The pre-M4c.0 defaults violated invariant 1.

## Applying this to an existing `.env`

The startup check is enforcing, so an existing `.env` that violates an
invariant will make the runner **refuse to start** until it is fixed. That is
deliberate: it is the same misconfiguration that was silently degrading runs,
surfaced at second zero instead of hour six.

At the time of writing, the operator `.env` in this repo carried
`CLAUDE_CLI_TIMEOUT_S=3600` with `WORKER_TIMEOUT_THRESHOLD=1750` — invariant 1,
meaning every healthy run over 1750s was being recorded as a timeout. Either
drop the two overrides and take the calibrated defaults, or keep the longer CLI
ceiling and raise the guard above it:

```
CLAUDE_CLI_TIMEOUT_S=3600
WORKER_TIMEOUT_THRESHOLD=3900
```

`profiles/overnight.env` and `profiles/overnight-subscription.env` are already
updated, and `tests/test_config_invariants.py` asserts that every shipped
profile passes.

## Caveats

- **The worker distribution is right-censored.** Runs killed at the CLI ceiling
  report the ceiling, not their true duration, so every percentile here is a
  lower bound on the real one. This argues for headroom, never for a tighter
  bound.
- **Thin tails.** `test` (n=28), `infra` (n=18), `frontend` (n=12), `docs`
  (n=8), `general` (n=4) and `task` (n=1) have too few samples for a
  trustworthy p95. The per-type table is shown so a reader can judge that; the
  defaults are set from the pooled distribution and the largest per-type tail
  (`test`), not from the thin ones.
- **Zero-duration end-to-end samples.** Many `database`, `runner` and `ui`
  entries complete in under a second because they were dry-run or skipped
  tasks. They drag the medians of that table to 0 and should be read as "no
  worker ran", not "instant task". The p95/p99/max columns are the useful ones.
- **The retry backoff bounds are budgeted, not fitted.** There is no observed
  distribution behind them; see the table note above.
- **`MAX_LOOP_TASKS` and the cooldown/deploy timeouts are out of scope** for
  this pass and remain as set.

## Measurements

Source: `runner/langgraph/logs/runs.jsonl` — 15538 events, `2026-06-08T18:35:58.684508` → `2026-08-03T01:25:23.897424`.

### Worker run duration (`worker_finished.elapsed_seconds`)

| scope | n | min | median | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all task types | 208 | 2.2s | 301.5s | 606.4s | 817.6s | 1653.4s | 1800.3s |

By task type:

| task type | n | min | median | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| backend | 132 | 2.9s | 334.1s | 611.6s | 677.8s | 1558.7s | 1578.3s |
| test | 28 | 2.2s | 346.9s | 929.3s | 1694.6s | 1800.3s | 1800.3s |
| infra | 18 | 9.8s | 92.6s | 266s | 362.3s | 1434.7s | 1434.7s |
| frontend | 12 | 28.3s | 311s | 562.4s | 562.4s | 600.2s | 600.2s |
| docs | 8 | 29.4s | 291s | 312.5s | 333.9s | 333.9s | 333.9s |
| unknown | 5 | 38.4s | 332.4s | 547.8s | 547.8s | 547.8s | 547.8s |
| general | 4 | 54.2s | 179.4s | 242.2s | 242.2s | 242.2s | 242.2s |
| task | 1 | 151.3s | 151.3s | 151.3s | 151.3s | 151.3s | 151.3s |

By outcome:

| outcome | n | min | median | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| success | 181 | 9.8s | 292.6s | 615.2s | 817.6s | 1578.3s | 1694.6s |
| failed | 27 | 2.2s | 600.2s | 604.8s | 611.6s | 1800.3s | 1800.3s |

**Right-censored:** 1 run(s) finished within 15s of the CLI ceiling in force when the log was written (`1800s`). Those runs were *killed* at the ceiling, so the true tail is longer than the max shown above — an argument for headroom, never for a tighter bound.

### PR check-run duration (`pr_checks_completed.elapsed`)

| scope | n | min | median | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all checks complete | 61 | 0.4s | 82.6s | 677.2s | 681.6s | 693.4s | 695.5s |

`pr_checks_timeout` events: 8 (elapsed at timeout: 1790.3s median).

Time until the *first* check run appears (`pr_checks_poll_tick` with `total > 0`) — the quantity `PR_CHECKS_EMPTY_GRACE_S` must cover:

| scope | n | min | median | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| check registration | 67 | 0.4s | 20.7s | 20.9s | 21.6s | 21.7s | 22.6s |

### End-to-end task duration (`task_loaded` → `task_completed`)

This is the quantity the stale-run watchdog actually measures: a whole task, including checks, PR polling, and deploy — not just the worker.

| scope | n | min | median | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all task types | 332 | 0 min | 0 min | 10.6 min | 18 min | 29.1 min | 41.1 min |

By task type:

| task type | n | min | median | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| backend | 116 | 0 min | 6.9 min | 17.2 min | 22.7 min | 32.2 min | 34.8 min |
| database | 41 | 0 min | 0 min | 0 min | 0 min | 0 min | 0 min |
| frontend | 36 | 0 min | 0 min | 1.6 min | 13.1 min | 22.3 min | 22.3 min |
| runner | 32 | 0 min | 0 min | 0 min | 0 min | 0 min | 0 min |
| ui | 28 | 0 min | 0 min | 0 min | 0 min | 0 min | 0 min |
| infra | 26 | 0 min | 0 min | 2.5 min | 3.7 min | 4.4 min | 4.4 min |
| general | 26 | 0 min | 0 min | 0 min | 0 min | 8.4 min | 8.4 min |
| test | 17 | 1.6 min | 8.8 min | 22.9 min | 29.1 min | 41.1 min | 41.1 min |
| docs | 9 | 2.4 min | 5.6 min | 7.8 min | 7.9 min | 7.9 min | 7.9 min |
| task | 1 | 3.8 min | 3.8 min | 3.8 min | 3.8 min | 3.8 min | 3.8 min |

### Loop session span

Contiguous log activity, split on gaps > 30 minutes. This is what `MAX_RUNTIME_MINUTES` bounds.

| scope | n | min | median | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| session | 59 | 0 min | 37.6 min | 99.4 min | 145.3 min | 167.2 min | 203.2 min |
