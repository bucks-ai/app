# Overnight Runner Settings Profile

**Profile file:** `profiles/overnight.env`

A curated `.env` preset for launching the runner unattended for an extended period
(up to 8 hours). Every setting is explained inline in the file; this document
describes the tuning philosophy and the changes from the standard defaults.

---

## Quick start

```bash
cp profiles/overnight.env .env
# fill in credentials (OPENAI_API_KEY, GITHUB_TOKEN, SLACK_WEBHOOK_URL, etc.)
python main.py setup   # validate config
python main.py run
```

---

## Design principles

### 1. Slack is mandatory
`SLACK_NOTIFY=true` is non-negotiable. An overnight run produces no live output
you can watch; the Slack digest is the morning audit trail.

### 2. Prefer clean stops over infinite spin
Three settings work together to terminate gracefully when things go wrong:

| Setting | Overnight | Default | Effect |
|---------|-----------|---------|--------|
| `MAX_CONSECUTIVE_FAILURES` | 2 | 3 | Trip circuit breaker sooner |
| `STALE_RUN_WARN_MINUTES` | 45 | 30 | Earlier Slack warning |
| `MAX_STALE_TASK_MINUTES` | 90 | 60 | Longer task window before hard stop |
| `SEEDED_MISSION_QUEUE_STRICT` | true | false | Clean stop when queue exhausted |

### 3. More retries, longer backoffs
Transient failures (network blips, rate limits, flaky worker starts) are more
likely over an 8-hour window. The profile absorbs them without alerting:

| Setting | Overnight | Default |
|---------|-----------|---------|
| `MAX_TASK_RETRIES` | 2 | 1 |
| `FAILURE_RETRY_BACKOFF_BASE_S` | 60.0 | 30.0 |
| `FAILURE_RETRY_BACKOFF_MAX_S` | 600.0 | 300.0 |
| `HTTP_RETRY_ATTEMPTS` | 5 | 3 |
| `HTTP_RETRY_MAX_WAIT_S` | 30.0 | 10.0 |

### 4. Safety gates stay on, but warn instead of block
Strict modes are kept `false` so a single borderline review score or quality-gate
edge case doesn't freeze the loop for hours while you sleep. All gates are still
enabled and will be logged and reported via Slack.

Gates in warn mode: `ACCEPTANCE_CRITERIA_STRICT_MODE`, `DEFINITION_OF_DONE_STRICT_MODE`,
`INDEPENDENT_CODE_REVIEW_STRICT_MODE`, `HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE`,
`BUSINESS_OUTPUT_RUBRICS_STRICT_MODE`, `LAUNCH_READINESS_SCORECARD_STRICT_MODE`.

### 5. Autonomous merge approval
`MERGE_APPROVAL_POLICY=auto` lets the runner merge without waiting for a human
reviewer. Switch to `require_approval_on_high` if you want the loop to pause on
high-risk merges (accepts a paused-overnight trade-off).

### 6. Live worker health ping enabled
`WORKER_HEALTH_LIVE_PING=true` adds ~200 ms per dispatch to confirm the worker
CLI actually starts. Worth the overhead overnight when nobody is watching to catch
a broken environment early.

### 7. Cost ceiling
`MAX_SESSION_COST_DOLLARS=25.0` caps overnight spend. Set to `0.0` to disable,
or adjust to your comfort level before launching.

### 8. Strategic pause every 5 tasks
`STRATEGIC_PAUSE_INTERVAL=5` triggers a strategic gate review every 5 completed
tasks. This prevents the runner from drifting on a long autonomous session.

### 9. Tighter context compression
`CONTEXT_COMPRESSION_MAX_TOKENS=8000` (vs default 12000) keeps worker prompts
lean across many tasks, reducing the risk of exceeding model context limits late
in a long run.

---

## Settings changed from defaults

| Variable | Overnight | Default | Reason |
|----------|-----------|---------|--------|
| `MAX_LOOP_TASKS` | 50 | 10 | 8-hour window fits many tasks |
| `VERCEL_POLL_TIMEOUT` | 300 | 180 | More patience for slow deploys |
| `VERCEL_POLL_INTERVAL` | 10 | 5 | Less polling pressure on Vercel API |
| `MAX_TASK_RETRIES` | 2 | 1 | More retries for transient failures |
| `MAX_CONSECUTIVE_FAILURES` | 2 | 3 | Fail fast — don't waste the night |
| `MAX_REPEATED_ERRORS` | 2 | 3 | Tighter repeated-error guard |
| `FAILURE_RETRY_BACKOFF_BASE_S` | 60.0 | 30.0 | Longer recovery window |
| `FAILURE_RETRY_BACKOFF_MAX_S` | 600.0 | 300.0 | Up to 10 min between retries |
| `WORKER_HEALTH_LIVE_PING` | true | false | Catch broken envs immediately |
| `WORKER_HEALTH_LIVE_PING_TIMEOUT_S` | 15.0 | 10.0 | Slightly more ping patience |
| `MAX_WORKER_TIMEOUTS` | 2 | 3 | Fail fast on stuck workers |
| `STALE_RUN_WARN_MINUTES` | 45 | 30 | Earlier Slack warning |
| `MAX_STALE_TASK_MINUTES` | 90 | 60 | Allow longer task durations |
| `MAX_SESSION_COST_DOLLARS` | 25.0 | 0.0 | Overnight cost ceiling |
| `STRATEGIC_PAUSE_INTERVAL` | 5 | 0 | Re-evaluate direction regularly |
| `SEEDED_MISSION_QUEUE_STRICT` | true | false | Clean stop when queue done |
| `MERGE_APPROVAL_POLICY` | auto | require_approval_on_high | Fully autonomous merges |
| `HTTP_RETRY_ATTEMPTS` | 5 | 3 | Ride out overnight network blips |
| `HTTP_RETRY_INITIAL_WAIT_S` | 2.0 | 1.0 | Less aggressive initial retry |
| `HTTP_RETRY_MAX_WAIT_S` | 30.0 | 10.0 | More patience for rate-limited services |
| `CONTEXT_COMPRESSION_MAX_TOKENS` | 8000 | 12000 | Lean prompts across a long session |

---

## What stays the same

All safety gates remain enabled. Auto-merge, auto-deploy, auto-repair, and all
quality review nodes are active. The only structural difference is that strict
modes are off so gates warn instead of halt.
