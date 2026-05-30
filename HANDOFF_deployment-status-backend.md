# Handoff: Deployment Status Backend

Branch: `feature/deployment-status-backend`
Date: 2026-05-21

---

## Summary

Added a full deployment status layer on top of the existing Vercel project creation backend. bucks.ai can now detect whether a generated Vercel project has an actual deployment, normalize its state, persist the result as activity logs, and expose it through a new refresh endpoint. The execution status backend has been updated to surface deployment failure, manual connection requirements, and live URLs from both stored project metadata and status refresh logs.

---

## Files Created

| File | Purpose |
|---|---|
| `src/types/deployment.ts` | `DeploymentProvider`, `DeploymentStatus`, `DeploymentEnvironment`, `DeploymentStatusRecord`, `DeploymentStatusResponse`, `RefreshDeploymentStatusResult` |
| `src/lib/vercel/deployment-status.ts` | `normalizeVercelDeploymentStatus`, `normalizeVercelDeploymentEnvironment`, `extractDeploymentUrl`, `getLatestVercelDeploymentForProject`, `refreshVercelDeploymentStatusForBusiness` |
| `src/app/api/vercel/refresh-deployment-status/route.ts` | `POST /api/vercel/refresh-deployment-status` — authenticated refresh endpoint |
| `HANDOFF_deployment-status-backend.md` | This file |

---

## Files Modified

| File | Change |
|---|---|
| `src/app/api/vercel/project-status/route.ts` | Replaced raw deployment list with normalized `latestDeployment` shape; added `storedMetadata` and typed warnings |
| `src/lib/execution/status.ts` | Added `resolveDeploymentUrl`, `isLatestDeploymentFailed`, `isManualConnectionRequired` helpers; updated milestones, blockers, next actions, and assets to use them |

---

## API Routes Added

### `POST /api/vercel/refresh-deployment-status`

Fetches the latest Vercel deployment for a business, normalizes the status, persists activity logs, and returns the result.

**Request body:**
```json
{ "businessId": "<uuid>" }
```

**Success response:**
```json
{
  "ok": true,
  "data": {
    "status": "ready",
    "deploymentUrl": "https://my-startup-abc.vercel.app",
    "deploymentId": "dpl_xxx",
    "environment": "production",
    "warnings": []
  }
}
```

**Status values:** `not_started` | `queued` | `building` | `ready` | `failed` | `canceled` | `unknown` | `manual_action_required`

**Error codes:**

| Code | HTTP | Meaning |
|---|---|---|
| `missing_supabase_env` | 503 | Supabase env vars absent |
| `invalid_input` | 400 | Missing or non-string `businessId` |
| `unauthenticated` | 401 | No valid session |
| `forbidden` | 403 | Wrong owner |
| `business_not_found` | 404 | Business not found |
| `vercel_project_missing` | 400 | No Vercel project stored for this business |
| `vercel_status_failed` | 500 | Internal refresh error |

If `VERCEL_TOKEN` is missing, the route returns `ok: true` with `status: "manual_action_required"` and the stored deployment URL (if any) rather than erroring.

---

### `GET /api/vercel/project-status?businessId=...` (updated)

Now returns a normalized `latestDeployment` object instead of a raw deployments array.

**Success response (project exists, token set):**
```json
{
  "ok": true,
  "data": {
    "project": {
      "projectId": "prj_xxx",
      "projectName": "my-startup",
      "dashboardUrl": "https://vercel.com/dashboard/my-startup",
      "gitRepoFullName": "owner/repo",
      "productionBranch": "main",
      "createdAt": "2026-05-13T..."
    },
    "latestDeployment": {
      "status": "ready",
      "deploymentUrl": "https://my-startup-abc.vercel.app",
      "deploymentId": "dpl_xxx",
      "environment": "production",
      "createdAt": "2026-05-13T...",
      "readyAt": "2026-05-13T..."
    },
    "storedMetadata": {
      "deploymentUrl": null
    },
    "warnings": []
  }
}
```

`latestDeployment` is `null` when no deployments exist or token is not set.

---

## Activity Logs Added

### `vercel_deployment_status_refreshed`
Written on every refresh. Metadata:
```json
{
  "provider": "vercel",
  "status": "<normalized-status>",
  "deploymentUrl": "<url-or-null>",
  "deploymentId": "<uid-or-null>",
  "projectId": "prj_xxx",
  "projectName": "my-startup",
  "environment": "production",
  "checkedAt": "<iso-timestamp>",
  "warnings": []
}
```

### `vercel_deployment_ready`
Written additionally when `status === "ready"` and a URL was extracted.

### `vercel_deployment_failed`
Written additionally when `status === "failed"`.

All three are categorized as `"vercel"` by the existing `log-categories.ts` `startsWith("vercel_")` rule.

---

## Deployment Status Model

| Vercel raw state | Normalized status |
|---|---|
| `QUEUED` | `queued` |
| `INITIALIZING` | `building` |
| `BUILDING` | `building` |
| `READY` | `ready` |
| `ERROR` | `failed` |
| `CANCELED` | `canceled` |
| _(unknown)_ | `unknown` |
| _(no deployments found)_ | `manual_action_required` |
| _(no VERCEL_TOKEN)_ | `manual_action_required` |

---

## Execution Status Changes

**New helper functions in `status.ts`:**
- `resolveDeploymentUrl(vercelProject, logs)` — returns live URL from stored metadata or latest `vercel_deployment_ready` log
- `isLatestDeploymentFailed(logs)` — returns true when most recent status event is a failure with no subsequent ready log
- `isManualConnectionRequired(logs)` — returns true when latest refresh found no deployments

**Milestones updated:**
- `deployment_available` — now uses `resolveDeploymentUrl`; clearer `blockedReason` message
- `ready_for_validation` — same

**Blockers updated:**
- `deployment_failed` (new, high) — when latest deployment failed
- `manual_git_connection_required` (new, medium) — when project exists but no deployments found
- `deployment_status_unknown` (existing) — shown only when no failure/manual case applies

**Next actions updated:**
- `refresh_deployment_status` (new) — when project exists but no live URL and no failure
- `open_vercel_project` (new) — always when project exists
- `connect_git_manually` (new, high priority) — when manual connection is required
- `start_customer_validation` — now reads URL from `resolveDeploymentUrl`

**Assets updated:**
- Deployment asset now resolves URL via `resolveDeploymentUrl`, so it appears even when the URL comes from a status refresh log rather than the original project creation log.

---

## How to Test

Requires `.env.local` with Supabase + Vercel credentials, `npm run dev` running, a valid Supabase session with a business that has a Vercel project.

```bash
# 1. Logged out — should return 401
curl -X POST http://localhost:3000/api/vercel/refresh-deployment-status \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>"}'
# → { ok: false, code: "unauthenticated" }

# 2. No Vercel project — should return 400
curl -b <session-cookie> -X POST http://localhost:3000/api/vercel/refresh-deployment-status \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid-without-vercel-project>"}'
# → { ok: false, code: "vercel_project_missing" }

# 3. Missing VERCEL_TOKEN — returns manual_action_required (not error)
# (temporarily remove VERCEL_TOKEN from .env.local)
curl -b <session-cookie> -X POST http://localhost:3000/api/vercel/refresh-deployment-status \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid-with-vercel-project>"}'
# → { ok: true, data: { status: "manual_action_required", ... } }

# 4. Happy path — returns normalized status
curl -b <session-cookie> -X POST http://localhost:3000/api/vercel/refresh-deployment-status \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid-with-vercel-project>"}'
# → { ok: true, data: { status: "ready"|"building"|..., deploymentUrl: ..., ... } }

# 5. Project status with deployment info
curl -b <session-cookie> \
  "http://localhost:3000/api/vercel/project-status?businessId=<uuid>"
# → { ok: true, data: { project: {...}, latestDeployment: {...}, storedMetadata: {...}, warnings: [] } }

# 6. Verify in Supabase:
#    agent_activity_logs should have vercel_deployment_status_refreshed rows
#    and optionally vercel_deployment_ready or vercel_deployment_failed rows
```

---

## Known Limitations

- **No webhook listener.** Deployment status is only updated on-demand via the refresh endpoint. Real-time status requires a Vercel webhook listener (not yet built).
- **`storedMetadata.deploymentUrl`** reflects only what was saved during project creation, not the live deployment URL. The `latestDeployment.deploymentUrl` from the API is the authoritative live URL.
- **One-deployment-at-a-time.** The refresh always looks at the newest deployment. Multiple parallel deployments (e.g., production + preview) are not differentiated.
- **PAT scope.** All API calls use the single `VERCEL_TOKEN` PAT. Per-user OAuth is deferred.
- **No UI wiring yet.** The refresh endpoint needs a frontend button to trigger it. The workspace UI reads execution status from the existing `/api/businesses/[id]/execution-status` route, which now surfaces the new blockers and next actions automatically.

---

## Next UI Integration Task

**Branch: `feature/deployment-status-ui`**

1. Add a "Refresh deployment status" button to the Deploy tab that POSTs to `/api/vercel/refresh-deployment-status`.
2. Show status badge: Live / Building / Failed / Not deployed / Manual connection required.
3. If status is `ready`, show the `deploymentUrl` as a "View live site" link.
4. If status is `manual_action_required`, show instructions to push to main or connect Git in Vercel.
5. Poll or show a "last checked" timestamp from the latest `vercel_deployment_status_refreshed` log.
