# Handoff: tool-permissions-ui

Branch: `feature/tool-permissions-ui`
Date: 2026-05-13

## Files Created

- `src/types/tool-permission-ui.ts` - frontend types for permission statuses, setup statuses, actions, business selector options, and backend-compatible response views.
- `src/lib/tool-permission-client.ts` - browser-safe `fetch()` client for `GET /api/tool-permissions?businessId=...`, `POST /api/tool-permissions`, and `PATCH /api/tool-permissions/[id]`.
- `src/components/tools/PermissionControlRoom.tsx` - interactive setup queue client component with loading, empty, demo, API-missing, and action states.
- `src/components/tools/PermissionToolCard.tsx` - per-tool permission card with requested scopes, risk, human gates, demo-connected clarity, and action controls.
- `src/components/tools/PermissionStatusPill.tsx` - status pill for permission/setup states.
- `src/components/tools/PermissionActionBar.tsx` - wraps permission actions: request approval, approve, mark human-required, mark demo connected, reject, reset.
- `src/components/tools/BusinessPermissionSelector.tsx` - saved-business selector that scopes the permission queue to a selected business.
- `HANDOFF_tool-permissions-ui.md` - this handoff.

## Files Modified

- `src/app/tools/page.tsx` - made `/tools` dynamic and loads existing signed-in businesses through current server helpers when Supabase/session data is available.
- `src/components/tools/ToolRegistryPage.tsx` - added the new “Permission Setup” section near the top while preserving the registry and autonomy constitution below.
- `src/components/dashboard/BusinessDetail.tsx` - added a “Tool Setup Queue” via `PermissionControlRoom` using the current business id.

## UI Components Added

- Permission setup control room for GitHub, Vercel, Supabase, Stripe, PostHog, Gmail/Workspace, Resend, Cloudflare, and OpenAI.
- Business selector for signed-in `/tools` users with saved businesses.
- Demo permission layer for signed-out or Supabase-unavailable states.
- Empty queue state with “Create setup queue.”
- API-unavailable state with: “Permission API not available yet. Merge backend branch first.”

## Routes Touched

- `/tools`
- `/dashboard/businesses/[id]`

## Expected Backend API Routes

- `GET /api/tool-permissions?businessId=...`
- `POST /api/tool-permissions`
- `PATCH /api/tool-permissions/[id]`

The client expects typed payloads containing `permissions` for list/seed responses and `permission` for update responses. It also tolerates nested `data` envelopes and older snake_case row fields where possible.

## Fallback Behavior

- Missing permission API routes show the backend-pending warning and render a read-only expected queue preview.
- Signed-out `/tools` users see a demo permission layer plus a `/login` CTA.
- Signed-in users without saved businesses see a `/intake` CTA: “Generate a blueprint to create a setup queue.”
- Demo-connected cards explicitly say no real external account has been connected yet.
- Risky tools clearly state that bucks.ai cannot accept terms, enter payment data, or sign contracts.

## Manual Test Plan

1. Run `npm run dev`.
2. Open `/tools` signed out and confirm the demo permission layer appears near the top.
3. Confirm the static preferred/extended registry and autonomy constitution still render below.
4. Sign in with Supabase and verify saved businesses appear in the selector if available.
5. Select a saved business and verify the permission API missing state appears until the backend branch is merged.
6. Open `/dashboard/businesses/[id]` while signed in and confirm the Tool Setup Queue appears below the blueprint/human-action panels.
7. Check mobile width around 390px: cards stack, action buttons wrap, and no horizontal overflow appears.
8. After backend routes are merged, use “Create setup queue” and the action buttons to verify API round trips.

## Known Limitations

- No backend routes were created in this branch.
- No real GitHub, Vercel, Stripe, Gmail, Cloudflare, Resend, PostHog, Supabase, or OpenAI external account is connected by this UI.
- Action buttons are disabled in demo/API-missing preview states.
- Full signed-in project-detail UI could not be browser-smoked without an active Supabase session in this environment.
- Existing Next.js workspace-root warning remains due multiple lockfiles.

## Verification

- `npm install` - completed.
- `npm run lint` - passed.
- `npm run build` - passed.
- `npm run dev -- -p 3004` - started successfully.
- Browser smoke checks:
  - `/tools` signed-out/demo state rendered.
  - `/tools` mobile viewport rendered the setup queue without obvious overflow.
  - `/dashboard/businesses/acme-analytics` returned the signed-out detail gate in this environment.

## Recommended Next Task

Merge the backend/API branch, then connect the action responses end to end and verify seeded permission records for a real signed-in saved business.
