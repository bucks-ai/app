# HANDOFF: Agent Runs v1

**Branch:** `feature/agent-runs-v1`
**Author:** Arnav (AI session, 2026-06-01)
**Status:** Ready for review and merge

---

## Purpose

Agent Runs v1 creates the first durable, queryable history layer for bucks.ai agent work.

Each agent run record captures what a bucks.ai agent did (or is inferred to have done) for a specific business — including title, status, source, trigger, output, artifacts, errors, and the activity log rows it was derived from.

This layer sits between the static Agent Registry v1 (what agents exist) and the future Operating Team UI (how runs are surfaced to founders).

---

## Files Created

| File | Purpose |
|------|---------|
| `src/types/agent-runs.ts` | All agent run TypeScript types |
| `src/lib/agents/runs.ts` | Helper functions: read, write, infer runs |
| `src/app/api/businesses/[id]/agent-runs/route.ts` | GET list + POST create |
| `src/app/api/businesses/[id]/agent-runs/infer/route.ts` | POST infer from activity logs |
| `supabase/agent-runs.sql` | SQL schema (must be applied manually) |
| `HANDOFF_agent-runs-v1.md` | This file |

## Files Modified

| File | Change |
|------|--------|
| `src/lib/agents/status.ts` | Optionally loads latest agent run per agent to surface `active` and `waiting_for_approval` statuses; falls back safely if table is missing |
| `src/types/execution.ts` | Added `"agent"` to `ExecutionTimelineEvent["category"]` union |
| `src/lib/execution/log-categories.ts` | Added `agent_run_*` activity type pattern → `"agent"` category |

---

## SQL File

**`supabase/agent-runs.sql`** — must be run manually in Supabase SQL Editor after merge.

Creates:
- `public.agent_runs` table
- `trg_agent_runs_updated_at` trigger (requires `set_updated_at()` from validation.sql)
- 7 indexes
- RLS policies (select/insert/update/delete own rows)

**Prerequisites:** `supabase/schema.sql` must have been applied. `supabase/validation.sql` should have been applied (provides `set_updated_at()` function). If validation.sql was not applied, uncomment the `set_updated_at` function block at the top of the file.

---

## API Routes Added

### GET `/api/businesses/[id]/agent-runs`
Returns the run list and summary for a business.

```json
{
  "ok": true,
  "data": {
    "summary": {
      "businessId": "...",
      "totalRuns": 12,
      "completedRuns": 11,
      "failedRuns": 1,
      "runningRuns": 0,
      "blockedRuns": 0,
      "waitingRuns": 0,
      "lastRunAt": "2026-06-01T00:00:00Z",
      "agentsCovered": ["blueprint", "repository", "scaffold"],
      "generatedAt": "2026-06-01T00:00:00Z"
    },
    "runs": [ ... ]
  }
}
```

If the `agent_runs` table has not been applied yet:
```json
{
  "ok": true,
  "data": {
    "summary": { "totalRuns": 0, ... },
    "runs": [],
    "_warning": "agent_runs table not yet applied"
  }
}
```

### POST `/api/businesses/[id]/agent-runs`
Create a new agent run manually.

Body:
```json
{
  "agentId": "blueprint",
  "title": "Blueprint generated",
  "summary": "...",
  "status": "completed",
  "source": "user_triggered",
  "trigger": "blueprint_generated",
  "input": {},
  "output": {},
  "artifacts": [],
  "error": null
}
```

### POST `/api/businesses/[id]/agent-runs/infer`
Back-fills agent runs from existing `agent_activity_logs`. Idempotent — skips logs already covered.

Response:
```json
{
  "ok": true,
  "data": {
    "created": 8,
    "skipped": 3
  }
}
```

**Error codes** (all routes):
- `unauthenticated` — no session
- `forbidden` — wrong owner
- `business_not_found` — business does not exist
- `invalid_input` — missing or malformed body
- `agent_runs_schema_missing` — `agent_runs` table not yet applied (503)
- `agent_run_create_failed` — DB write failed
- `agent_run_update_failed` — DB update failed
- `agent_runs_infer_failed` — inference process failed

---

## Helper Functions Added

| Function | Purpose |
|----------|---------|
| `getAgentRunsForBusiness(businessId)` | Load all runs for a business, newest first |
| `getAgentRunSummaryForBusiness(businessId)` | Aggregate counts + last run timestamp |
| `createAgentRun(input)` | Insert a new agent run |
| `updateAgentRun(input)` | Update an existing run by id |
| `createAgentRunFromActivityLog(log)` | Convert one activity log to zero or more runs |
| `inferAgentRunsFromActivityLogs(businessId)` | Back-fill all activity logs idempotently |
| `getLatestRunForAgent(businessId, agentId)` | Fetch the most recent run for a specific agent |
| `toTimelineItems(runs)` | Convert run records to lightweight timeline items |

All functions return `{ data, error: null }` or `{ data: null, error: string, code: string }`. They never throw on missing tables — `agent_runs_schema_missing` is returned instead.

---

## Activity-to-Agent Mapping

| Activity Type | Agent(s) | Trigger |
|--------------|----------|---------|
| `blueprint_created` / `business_blueprint_saved` | `blueprint` | `blueprint_generated` |
| `github_repo_created` | `repository` | `repo_created` |
| `github_next_scaffold_prepared` / `scaffold_prepared` | `scaffold` | `scaffold_prepared` |
| `vercel_project_created` | `deployment_status` | `vercel_project_created` |
| `deployment_status_refreshed` / `deployment_ready` / `deployment_failed` | `deployment_status` | `deployment_status_refreshed` |
| `validation_workspace_seeded` | `persona`, `hypothesis` | `validation_workspace_seeded` |
| `validation_feedback_added` | `feedback_analysis` | `manual` |
| `research_workspace_generated` | `market_research`, `customer_segment`, `competitor`, `monetization`, `distribution`, `risk` | `research_workspace_generated` |
| `research_report_created` | `opportunity_scoring` | `research_workspace_generated` |
| `tool_permissions_seeded` / `tool_permission_approved` | `tool_permission` | `tool_permission_approved` |
| `next_action_resolved` | `next_action` | `next_action_resolved` |

Unmapped activity types are skipped silently (no run created, skipped counter incremented).

---

## How to Apply SQL Manually

1. Merge `feature/agent-runs-v1` into `main`
2. Go to [Supabase Dashboard](https://supabase.com) → your project → SQL Editor
3. Paste the full contents of `supabase/agent-runs.sql`
4. Click **Run**
5. Verify: `SELECT COUNT(*) FROM agent_runs;` returns `0` (table exists, empty)
6. Run `/api/businesses/[id]/agent-runs/infer` to back-fill from existing activity logs

---

## Manual Test Plan

After applying `supabase/agent-runs.sql`:

```bash
# 1. Unauthenticated — expect 401
curl http://localhost:3000/api/businesses/SOME_ID/agent-runs

# 2. Wrong owner — expect 403
# Sign in as user A, request business owned by user B

# 3. Valid owner, before SQL applied — expect 200 with empty runs + _warning
# (The GET route handles schema_missing gracefully)

# 4. After SQL applied — GET returns empty runs
curl -b session-cookie http://localhost:3000/api/businesses/YOUR_ID/agent-runs

# 5. Infer from activity logs
curl -X POST -b session-cookie \
  http://localhost:3000/api/businesses/YOUR_ID/agent-runs/infer
# → { ok: true, data: { created: N, skipped: M } }

# 6. Run inference again — should be idempotent
curl -X POST -b session-cookie \
  http://localhost:3000/api/businesses/YOUR_ID/agent-runs/infer
# → { ok: true, data: { created: 0, skipped: N } }

# 7. GET runs after inference
curl -b session-cookie http://localhost:3000/api/businesses/YOUR_ID/agent-runs
# → runs array populated, summary.totalRuns > 0

# 8. Create a manual run
curl -X POST -b session-cookie \
  -H "Content-Type: application/json" \
  -d '{"agentId":"blueprint","title":"Test run","source":"manual_note"}' \
  http://localhost:3000/api/businesses/YOUR_ID/agent-runs
# → 201 with created run

# 9. Agent Registry still works without agent_runs SQL applied
curl -b session-cookie http://localhost:3000/api/businesses/YOUR_ID/agents
# → 200 with 21 agents (no crash if agent_runs table missing)
```

---

## Known Limitations

1. **Back-fill is approximate** — one activity log may map to multiple runs (e.g. `validation_workspace_seeded` creates both a persona run and a hypothesis run). This is by design.
2. **No deduplication beyond activity log IDs** — if the same log is re-processed (e.g. re-created in the DB), a duplicate run could be created. Covered by the `coveredLogIds` set within a single inference pass, but not across passes if log IDs change.
3. **No partial-run support** — `running` status runs require external code to create them. This task only creates `completed` / back-filled runs.
4. **No pagination** — all runs returned in a single query. Fine for MVP.
5. **Status enhancement is limited** — only `running` → `active` and `waiting_for_approval` overrides are applied. Completed/failed run statuses from runs are not used to downgrade a `completed` activity-log status.
6. **No run output search** — `output` and `artifacts` are stored as JSONB but not indexed for search.

---

## Intentionally Deferred

| Feature | Reason |
|---------|--------|
| Operating Team UI | Separate task |
| Workflow graph engine | Future milestone |
| Autonomous / self-creating agents | Not in MVP scope |
| Retry / resume engine | Requires run lifecycle management |
| Evaluator layer | Requires LLM execution sessions |
| Tool call logs | Requires execution tracing |
| Multi-agent conversations | Requires orchestration graph |
| Real-time run streaming | Requires WebSocket / SSE infrastructure |
