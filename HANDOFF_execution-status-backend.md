# Handoff: execution-status-backend

Branch: `feature/execution-status-backend`
Date: 2026-05-17

## Files Created

- `src/types/execution.ts` - shared execution status, milestone, timeline, blocker, next-action, and asset contracts.
- `src/lib/execution/status.ts` - read-only execution status builder over existing Supabase records and activity logs.
- `src/lib/execution/log-categories.ts` - activity log category helper for blueprint, permissions, GitHub, Vercel, human, system, and other events.
- `src/app/api/businesses/[id]/execution-status/route.ts` - authenticated owner-only status API.
- `src/app/api/businesses/[id]/execution-timeline/route.ts` - authenticated owner-only timeline API.
- `HANDOFF_execution-status-backend.md` - this handoff.

## Files Modified

- `src/app/api/github/create-repo/route.ts` - adds richer metadata to future `github_repo_created` logs.
- `src/lib/github/next-scaffold.ts` - adds richer metadata to future `github_next_scaffold_prepared` logs.
- `src/app/api/vercel/create-project/route.ts` - adds richer metadata to future `vercel_project_created` logs.

## API Routes Created

### `GET /api/businesses/[id]/execution-status`

Returns:

```json
{
  "ok": true,
  "data": {}
}
```

`data` is a `BusinessExecutionStatus`.

Error shape:

```json
{
  "ok": false,
  "code": "unauthenticated",
  "error": "Authentication required."
}
```

Codes include `missing_supabase_env`, `unauthenticated`, `not_found`, `forbidden`, and `execution_status_failed`.

### `GET /api/businesses/[id]/execution-timeline`

Returns timeline events only for lightweight refreshes:

```json
{
  "ok": true,
  "data": []
}
```

Codes include `missing_supabase_env`, `unauthenticated`, `not_found`, `forbidden`, and `execution_timeline_failed`.

## Data Sources Used

- `businesses`
- `business_blueprints`
- `human_required_actions`
- `agent_activity_logs`
- `tool_permissions`
- GitHub repo metadata from `getLatestGitHubRepoForBusiness`
- Vercel project metadata from `getLatestVercelProjectForBusiness`

No new database tables were added. `agent_activity_logs` remains the system of record for execution timeline and external asset metadata.

## Milestone Model

The status helper emits these milestones:

1. Idea captured
2. Blueprint generated
3. Tool permissions seeded
4. GitHub approved
5. GitHub repo created
6. Deployable scaffold prepared
7. Vercel approved
8. Vercel project created
9. Deployment available
10. Ready for validation

Statuses are `complete`, `in_progress`, `blocked`, `not_started`, or `warning`. Progress is a weighted percentage: complete milestones count fully, warnings count 75%, and in-progress milestones count 50%.

## Blocker Model

Blockers are derived from missing required records and known denied states:

- missing blueprint
- GitHub not approved
- GitHub repo missing after approval
- Vercel not approved
- Vercel project missing after approval
- pending human-required actions
- rejected or blocked tool permissions
- Vercel project exists but deployment URL is unknown

Each blocker includes severity, a recommended action, and a related tool id where applicable.

## Next Action Model

Next actions are deterministic from the same inputs:

- Generate blueprint
- Review pending human actions
- Approve GitHub
- Create GitHub repo
- Prepare deployable scaffold
- Approve Vercel
- Create Vercel project
- Start customer validation

Each action is assigned to either `founder` or `bucks_ai` with high, medium, or low priority.

## How To Test

Requires `.env.local` with Supabase credentials and a signed-in browser/session for owner checks.

```bash
./scripts/check.sh
```

Manual API smoke tests:

```bash
# logged out should return 401 when Supabase env is configured
curl http://localhost:3000/api/businesses/<business-id>/execution-status

# owner session should return BusinessExecutionStatus
curl -b <session-cookie> http://localhost:3000/api/businesses/<business-id>/execution-status

# owner session timeline-only refresh
curl -b <session-cookie> http://localhost:3000/api/businesses/<business-id>/execution-timeline

# another user's business should return 403 or 404 depending on RLS visibility
curl -b <session-cookie> http://localhost:3000/api/businesses/<other-business-id>/execution-status
```

Recommended scenario checks:

- Business with no blueprint returns a `no_blueprint` blocker and a `Generate blueprint` next action.
- Business with seeded but unapproved GitHub shows `GitHub not approved`.
- Business with GitHub approved and no repo shows `Create GitHub repo`.
- Business with repo and Vercel approved but no Vercel project shows `Create Vercel project`.
- Business with Vercel project but no deployment URL shows `deployment_status_unknown`.
- Business with repo/Vercel activity logs exposes those assets and timeline categories.

## Known Limitations

- Status is inferred from current records and activity logs; there is no snapshot table or historical state machine yet.
- Existing older activity logs will not have the new `assetType`, `status`, or `executionPhase` metadata fields, but they remain supported.
- Deployment availability uses stored Vercel metadata only. It does not call Vercel live status from the execution-status endpoint.
- Pending human action status is interpreted broadly because the current schema stores status as free text.
- There is no pagination on timeline events yet.

## Recommended Next Task

Wire the business detail UI to `GET /api/businesses/[id]/execution-status` and replace scattered status panels with the unified milestones, blockers, next actions, assets, and timeline model.
