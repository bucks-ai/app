# Handoff: Vercel Deploy Status Gate

Branch: `feature/runner-vercel-deploy-status-gate`
Date: 2026-06-08

---

## Summary

Added a reusable **deploy status gate** on top of the existing Vercel deployment-status
layer. The gate answers a single question — *is this business's deployment in a state
that should permit deploy-dependent actions (e.g. starting customer validation against a
live URL)?* — and returns a machine-readable pass/blocked verdict with a reason code.

It exposes a pure decision function (`decideDeploymentGate`) that other server code can
reuse without any network calls, a live evaluator (`evaluateDeploymentGate`) that resolves
status from stored metadata + the Vercel API (with a log/metadata fallback when no token is
configured), and a read-only API route to query the verdict.

---

## Files Created

| File | Purpose |
|---|---|
| `src/lib/vercel/deploy-gate.ts` | `decideDeploymentGate` (pure verdict) and `evaluateDeploymentGate` (live, read-only evaluation) |
| `src/app/api/vercel/deploy-gate/route.ts` | `GET /api/vercel/deploy-gate?businessId=...` — authenticated gate verdict |
| `HANDOFF_vercel-deploy-status-gate.md` | This file |

## Files Modified

| File | Change |
|---|---|
| `src/types/deployment.ts` | Added `DeploymentGateCode` and `DeploymentGateResult` types |

---

## API Route Added

### `GET /api/vercel/deploy-gate?businessId=...`

Returns the gate verdict. The decision is always returned with HTTP 200 in `data`;
non-200s are reserved for auth/ownership/input failures (mirrors `project-status`).

**Success response:**
```json
{
  "ok": true,
  "data": {
    "passed": false,
    "code": "deployment_in_progress",
    "status": "building",
    "reason": "A deployment is in progress. Wait for it to finish, then try again.",
    "deploymentUrl": null,
    "projectId": "prj_xxx",
    "checkedAt": "2026-06-08T...",
    "warnings": []
  }
}
```

`deploymentUrl` is populated only when `passed` is `true`.

**Gate codes:** `ready` | `no_vercel_project` | `no_deployment_found` |
`deployment_in_progress` | `deployment_failed` | `deployment_canceled` |
`manual_action_required` | `status_unknown`

**Error codes:**

| Code | HTTP | Meaning |
|---|---|---|
| `missing_supabase_env` | 503 | Supabase env vars absent |
| `invalid_input` | 400 | Missing `businessId` |
| `unauthenticated` | 401 | No valid session |
| `business_not_found` | 404 | Business not found |
| `forbidden` | 403 | Wrong owner |

---

## Gate Decision Model

`decideDeploymentGate({ hasProject, status, deploymentUrl })` maps a normalized
`DeploymentStatus` to a verdict:

| Condition | Code | Passed |
|---|---|---|
| no Vercel project | `no_vercel_project` | ❌ |
| `ready` + live URL | `ready` | ✅ |
| `ready`, no URL | `status_unknown` | ❌ |
| `queued` / `building` | `deployment_in_progress` | ❌ |
| `failed` | `deployment_failed` | ❌ |
| `canceled` | `deployment_canceled` | ❌ |
| `manual_action_required` | `manual_action_required` | ❌ |
| `not_started` | `no_deployment_found` | ❌ |
| `unknown` | `status_unknown` | ❌ |

`evaluateDeploymentGate(businessId)` resolves the status before applying the decision:

1. No Vercel project stored → `no_vercel_project`.
2. `VERCEL_TOKEN` missing → falls back to the stored `vercelDeploymentUrl` or the latest
   `vercel_deployment_ready` activity log; passes only if a ready URL is found, otherwise
   `manual_action_required` (with a warning).
3. Token present → fetches the latest deployment via `getLatestVercelDeploymentForProject`,
   normalizes its state, and applies `decideDeploymentGate`.

The evaluator is **read-only** — it writes no activity logs, so it is safe to call from any
route handler (including before a deploy-dependent mutation).

---

## How to Test

Requires `.env.local` with Supabase (+ optionally Vercel) credentials, `npm run dev`
running, and a valid Supabase session.

```bash
# 1. Logged out — 401
curl "http://localhost:3000/api/vercel/deploy-gate?businessId=<uuid>"
# → { ok: false, code: "unauthenticated" }

# 2. No businessId — 400
curl -b <session> "http://localhost:3000/api/vercel/deploy-gate"
# → { ok: false, code: "invalid_input" }

# 3. No Vercel project — passed:false, code:no_vercel_project
curl -b <session> "http://localhost:3000/api/vercel/deploy-gate?businessId=<uuid-no-project>"

# 4. Project exists, no token — manual_action_required (or ready from stored URL)
curl -b <session> "http://localhost:3000/api/vercel/deploy-gate?businessId=<uuid-with-project>"

# 5. Live ready deployment — passed:true, code:ready, deploymentUrl set
curl -b <session> "http://localhost:3000/api/vercel/deploy-gate?businessId=<uuid-deployed>"
```

`./scripts/check.sh` (lint + build) passes.

---

## Known Limitations

- **Not yet enforced anywhere.** The gate is a standalone primitive + endpoint. No existing
  route (e.g. customer-validation seed) calls it yet — enforcement is intentionally left to a
  follow-up so current flows are unchanged.
- **No caching / no logging.** Every call hits the Vercel API live when a token is present.
  Unlike `refresh-deployment-status`, the gate writes no activity logs.
- **Production-first.** Like the rest of the deployment-status layer, it evaluates the single
  newest deployment and does not distinguish production vs preview targets.
- **PAT scope.** Uses the single shared `VERCEL_TOKEN`; per-user OAuth is still deferred.

---

## Recommended Next Task

**Branch: `feature/vercel-deploy-gate-enforcement`**

1. Call `evaluateDeploymentGate` (or `decideDeploymentGate` against already-loaded status) in
   the customer-validation start path and return `409 deployment_not_ready` with the gate
   `reason` when `passed` is false — behind an explicit `force` override for founder-led
   validation that intentionally precedes deploy.
2. Surface the gate verdict in `GET /api/businesses/[id]/execution-status` so the UI has a
   single authoritative readiness flag instead of recomputing deployment blockers.
3. Add a "deployment not ready" banner + retry on the validation tab driven by the gate code.
