# Handoff: project-persistence

Branch: `feature/project-persistence`
Date: 2026-05-12

## Files Created

- `src/app/api/businesses/save-blueprint/route.ts` - authenticated API route that saves generated intake blueprints as Supabase business projects.
- `HANDOFF_project-persistence.md` - this handoff document.

## Files Modified

- `src/lib/projects.ts` - expanded human-required action extraction to support `humanRequiredActions`, permission gates, approval gates, and risk fallback data.
- `src/components/intake/IdeaIntakeWizard.tsx` - checks the browser Supabase session after real blueprint generation and saves authenticated blueprints.
- `src/components/intake/BlueprintPreview.tsx` - shows save progress, saved dashboard link, signup CTA, and non-blocking save warnings.
- `src/app/dashboard/page.tsx` - replaced the default mock dashboard with server-side Supabase data when signed in, plus setup and signed-out preview states.
- `src/app/dashboard/businesses/[id]/page.tsx` - replaced static mock detail records with dynamic Supabase business, blueprint, action, and activity loading.
- `src/components/dashboard/ActivityLog.tsx` - supports a neutral real-log label instead of always implying sample data.
- `src/components/dashboard/BusinessCard.tsx` - supports real/sampled source labels.
- `src/components/dashboard/BusinessDetail.tsx` - supports real human action rows and empty states.
- `src/components/dashboard/mock-data.ts` - extended shared dashboard display types.

## API Route Created

`POST /api/businesses/save-blueprint`

Request body:

```json
{
  "startupIdea": {},
  "blueprint": {}
}
```

Success response:

```json
{
  "ok": true,
  "businessId": "...",
  "detailUrl": "/dashboard/businesses/..."
}
```

Error response:

```json
{
  "ok": false,
  "error": "...",
  "code": "..."
}
```

Behavior:

- Returns `503` when public Supabase env vars are missing.
- Returns `401` when no authenticated Supabase session exists.
- Returns `400` for invalid JSON or missing required payload fields.
- Creates a `businesses` row, `business_blueprints` row, human-required actions, and an initial `agent_activity_logs` row.
- Uses the normal Supabase server client and RLS. It does not use `SUPABASE_SERVICE_ROLE_KEY`.

## Dashboard Behavior

- `/dashboard` is dynamic and uses `getCurrentUser()` plus `getUserBusinesses()`.
- Signed-in users see real saved businesses, recent saved activity logs, and pending human-required actions.
- Signed-in users with no saved businesses see an empty state linking back to `/intake`.
- Signed-out users see a sign-in/create-account CTA and a sample preview clearly labeled as sample data.
- Missing Supabase env vars show a setup panel and sample preview.

## Business Detail Behavior

- `/dashboard/businesses/[id]` is dynamic and no longer uses mock `generateStaticParams()`.
- The page loads the business by id, checks ownership against the current authenticated user, then loads latest blueprint, human-required actions, and activity logs.
- Missing records or records outside the user's RLS scope show a clean not-found/unauthorized state.
- Suggested tools from the saved blueprint are displayed as deferred permission suggestions.

## Intake Save Behavior

- `/intake` still allows unauthenticated blueprint generation.
- After a real OpenAI blueprint succeeds, the client checks Supabase auth with the browser client.
- Authenticated users call `POST /api/businesses/save-blueprint`.
- Successful saves show "Saved to Mission Control" and a link to the saved business detail page.
- Signed-out users see "Create an account to save this build" with a `/signup` CTA.
- Save failures are non-blocking and keep the generated blueprint visible with "Blueprint generated, but saving failed."
- Demo fallback blueprints are not saved automatically.

## Environment Variables Required

For persistence:

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

For real blueprint generation:

```env
OPENAI_API_KEY=
```

`SUPABASE_SERVICE_ROLE_KEY` may remain useful for backend/admin work from the data-layer branch, but this persistence flow does not use it.

## How To Test Authenticated Save

1. Ensure Supabase schema has been run.
2. Set `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `OPENAI_API_KEY` in `.env.local`.
3. Start the app with `npm run dev`.
4. Sign in with the auth branch/session flow.
5. Visit `/intake`, fill required fields, and generate a real blueprint.
6. Confirm the preview shows "Saved to Mission Control".
7. Open the dashboard link and confirm `/dashboard/businesses/[id]` shows the saved blueprint, actions, and activity log.
8. Visit `/dashboard` and confirm the saved business appears in the real list.

## How To Test Unauthenticated Generation

1. Start the app without a Supabase session.
2. Visit `/intake`.
3. Generate a real blueprint if `OPENAI_API_KEY` exists, or use the existing demo fallback if it does not.
4. Confirm generation is not blocked by auth.
5. For real generation while signed out, confirm the preview shows "Create an account to save this build".
6. Visit `/dashboard` and confirm the preview is clearly labeled as sample data.

## Known Limitations

- The save route performs multiple sequential inserts without a database transaction because the existing helper layer does not expose an RPC/transaction wrapper.
- Dashboard list cards show business metadata and aggregate queues; full blueprint detail is on the business detail route.
- Tool permissions are still display-only suggestions derived from the blueprint. No live integrations are connected.
- Auth UI/session creation is intentionally handled by the parallel auth branch.

## Verification

- `npm run lint` - passed.
- `npm run build` - passed. Existing Next.js workspace-root warning remains due multiple lockfiles.
- `npm run dev` - started on `http://localhost:3003` because port `3000` was already in use, then stopped after smoke checks.
- Smoke checks:
  - `GET /intake` returned `200`.
  - `GET /dashboard` returned `200` and showed signed-out/sample preview state.
  - `GET /dashboard/businesses/not-a-real-id` returned `200` and showed signed-out detail CTA.
  - `POST /api/businesses/save-blueprint` with an empty body returned `400 invalid_startup_idea`.
  - `POST /api/businesses/save-blueprint` with a valid payload and no session returned `401 not_authenticated`.

## Intentionally Deferred

- Login/signup behavior changes.
- Middleware or protected-route rewrites.
- GitHub, Vercel, Stripe, outreach, CRM, billing, or deployment integrations.
- Editing or approving human-required actions.
- Re-generating or versioning blueprints from the dashboard.

## Recommended Next Task

Wire the auth branch into this persistence flow and verify the end-to-end signed-in save path against the live Supabase project.
