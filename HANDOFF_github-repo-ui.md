# Handoff: github-repo-ui

Branch: `feature/github-repo-ui`
Date: 2026-05-13

## Files Created

- `src/types/github-ui.ts` - typed GitHub repo visibility, request input, UI state, result, and success/error response contracts.
- `src/lib/github-client.ts` - browser-safe `fetch()` client for `POST /api/github/create-repo` with friendly fallbacks for missing backend, missing token, permission blocks, invalid responses, and network errors.
- `src/components/github/GitHubRepoCard.tsx` - client-side repo creation form with default private visibility, starter-file checkbox, loading, success, warnings, and readable error states.
- `src/components/github/GitHubRepoResult.tsx` - success/existing-repo display with repo URL, full name, private/public pill, and warning copy.
- `src/components/github/GitHubRepoGate.tsx` - approval gate explaining that GitHub must be approved in the Tool Setup Queue first.
- `HANDOFF_github-repo-ui.md` - this handoff.

## Files Modified

- `src/components/dashboard/BusinessDetail.tsx` - added the “Repository Execution” section after the Tool Setup Queue, gates GitHub repo creation on approved/demo-connected GitHub permission when permission data is available, and falls back to rendering the guarded card when permission data is absent.
- `src/app/dashboard/businesses/[id]/page.tsx` - fetches tool permission rows for the business, preserves enough permission state for frontend gating, and detects the latest `github_repo_created` activity log metadata for existing repo display.
- `src/components/dashboard/mock-data.ts` - extended dashboard business shape with optional one-line idea, tool permission status summaries, and existing GitHub repo result.

## UI Components Added

- Controlled GitHub repository execution card.
- GitHub permission-required gate with Tool Setup Queue anchor link.
- Existing/success GitHub repo result display.
- “Create another repo” expansion path when an existing repo is already recorded.

## Expected Backend Route

`POST /api/github/create-repo`

Request body:

```json
{
  "businessId": "business-id",
  "repoName": "repo-name",
  "visibility": "private",
  "includeStarterFiles": true
}
```

Expected success:

```json
{
  "ok": true,
  "data": {
    "repoUrl": "https://github.com/owner/name",
    "fullName": "owner/name",
    "owner": "owner",
    "name": "name",
    "private": true
  },
  "warning": "optional warning"
}
```

Expected error:

```json
{
  "ok": false,
  "code": "permission_required",
  "error": "Approve GitHub in Tool Setup Queue first."
}
```

## Safety Copy Included

- This creates a real GitHub repo using the server-side dev token.
- Repo defaults to private.
- No production app code is generated.
- No deployment is triggered.
- No billing or payment action happens.
- Founder approval is required before bucks.ai creates external assets.
- bucks.ai will not create external assets without founder approval.

## Manual Test Plan

1. Run `npm run dev`.
2. Open `/dashboard/businesses/[id]` while signed in with a saved business.
3. Confirm the Tool Setup Queue appears before “Repository Execution.”
4. With GitHub not approved, confirm the gate appears and links back to `#tool-setup-queue`.
5. Approve or demo-connect GitHub in the Tool Setup Queue, then confirm the repo card appears.
6. Edit the repo name and confirm the input updates without layout shift.
7. Toggle visibility and starter files.
8. Click “Create GitHub repo.”
9. If the backend route is not merged, confirm: “GitHub backend route is not available yet. Merge backend branch first.”
10. If the server token is missing, confirm: “GitHub token is not configured on the server.”
11. If permission is rejected by the backend, confirm: “Approve GitHub in Tool Setup Queue first.”
12. With a successful backend response, confirm the repo URL appears and no duplicate create form is shown unless “Create another repo” is expanded.

## Known Limitations

- No backend GitHub API route was created in this branch.
- No GitHub token, OAuth flow, GitHub App setup, deployment, or server helper changes were added.
- Existing repo detection depends on an activity log with `activity_type = "github_repo_created"` and metadata containing repo URL/full name data.
- Signed-out/manual browser smoke of the authenticated project detail page depends on having a local Supabase session.
- The existing Next.js workspace-root warning remains due multiple lockfiles.

## Verification

- `npm install` - completed.
- `npm run lint` - passed.
- `npm run build` - passed with the existing multiple-lockfile workspace-root warning.
- `npm run dev` - started successfully on `http://localhost:3003` because port `3000` was occupied.
- Browser smoke check - `/dashboard` rendered the signed-out state and sample business cards; `/dashboard/businesses/acme-analytics` rendered the signed-out detail gate in this browser session, so authenticated Repository Execution UI still needs a signed-in Supabase session for manual QA.

## Recommended Next Task

Merge the backend branch that implements `POST /api/github/create-repo`, then run the manual test plan against a real signed-in saved business and verify the `github_repo_created` activity log metadata shape.
