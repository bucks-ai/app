# Handoff: vercel-deployment-ui

Branch: `feature/vercel-deployment-ui`
Date: 2026-05-13

## Files Created

- `src/types/vercel-ui.ts` - frontend Vercel deployment types for create state, project result, status response, create response, scaffold response, and serializable activity logs.
- `src/lib/vercel-client.ts` - browser-safe `fetch()` client for scaffold prep, project creation, and stored status lookup with friendly backend-pending and Vercel-specific errors.
- `src/components/vercel/VercelDeployGate.tsx` - approval/source-repo gate for deployment execution.
- `src/components/vercel/VercelProjectCard.tsx` - project creation form with project name, scaffold/deployment checkboxes, loading, success, warnings, and friendly errors.
- `src/components/vercel/VercelProjectResult.tsx` - success/existing-project display with dashboard and deployment links.
- `src/components/vercel/DeploymentExecutionPanel.tsx` - orchestrates GitHub repo gate, Vercel approval gate, scaffold prep, project creation, and stored project state.
- `src/components/vercel/ScaffoldPrepCard.tsx` - standalone scaffold preparation action with expected file list.
- `HANDOFF_vercel-deployment-ui.md` - this handoff.

## Files Modified

- `src/components/dashboard/BusinessDetail.tsx` - added Deployment Execution after Repository Execution and reordered detail content so blueprint/actions/logs appear before Tool Setup Queue.
- `src/app/dashboard/businesses/[id]/page.tsx` - passes serializable activity logs, detects GitHub metadata variants, and detects recorded `vercel_project_created` metadata.
- `src/components/dashboard/mock-data.ts` - extended `DashboardBusiness` with activity logs and optional Vercel project result.
- `src/components/ui/OperatorPanel.tsx` - added optional `id` support for section anchors.
- `AI_CHANGELOG.md` - added this session entry.
- `TASKS.md` - added the Vercel deployment UI item to Done.
- `PROJECT_STATE.md` - updated current working feature/integration status.

## UI Sections Added

- Deployment Execution panel on saved business detail pages.
- GitHub repo required gate.
- Vercel approval required gate.
- Standalone Next.js scaffold prep card.
- Vercel project creation card.
- Recorded/success Vercel project result with dashboard/deployment links.

## Expected Backend Routes

- `POST /api/github/prepare-next-scaffold`
- `POST /api/vercel/create-project`
- `GET /api/vercel/project-status?businessId=...`

The UI treats `404` and `405` as backend-pending and shows: “Vercel backend route is not available yet. Merge backend branch first.”

## Safety Copy

The UI states that deployment execution:

- Creates a real Vercel project.
- Uses a server-side Vercel token.
- Does not copy the current app's secrets.
- Does not create a custom domain.
- Does not create payments or send emails.
- Does not use production customer data.
- Is approval-gated by the Vercel tool permission.

## Manual Test Plan

1. Run `npm run dev`.
2. Open `/dashboard/businesses/[id]` while signed in with a saved business.
3. Confirm the order: overview, blueprint/action/log panels, Tool Setup Queue, Repository Execution, Deployment Execution.
4. With no recorded GitHub repo, confirm Deployment Execution shows “Create a GitHub repo first.”
5. With a GitHub repo recorded but Vercel not approved, confirm it shows “Approve Vercel in Tool Setup Queue first.”
6. With GitHub repo recorded and Vercel approved or `connected_demo`, confirm scaffold and project cards render.
7. Click “Prepare starter scaffold” and confirm it calls `POST /api/github/prepare-next-scaffold`.
8. Click “Create Vercel project” and confirm it calls `POST /api/vercel/create-project`.
9. Refresh after a recorded `vercel_project_created` activity log and confirm dashboard/deployment links render.
10. Check a mobile viewport around 390px and confirm cards stack without horizontal overflow.

## Verification

- `npm install` - completed before work.
- `./scripts/check.sh` - passed after one TypeScript fix.
- `npm run dev -- -p 3005` - started successfully.
- Browser smoke - `/dashboard/businesses/acme-analytics` rendered the signed-out detail gate in this local session, so signed-in deployment states still need manual QA with a Supabase session.

## Known Limitations

- No backend Vercel API routes were created in this branch.
- No tokens, OAuth, custom domains, emails, payment setup, or server Vercel helpers were added.
- Stored status depends on backend route response or `agent_activity_logs` metadata with `activity_type = "vercel_project_created"`.
- Full authenticated browser QA was not possible in this session because the browser was signed out.
- Existing Next.js workspace-root warning remains due multiple lockfiles.

## Recommended Next Task

Merge the backend branch for scaffold/project/status routes, then run the manual test plan against a signed-in saved business with GitHub and Vercel permissions seeded.
