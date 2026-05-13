# Handoff: backend-data-layer

Branch: `feature/backend-data-layer`
Date: 2026-05-12

---

## Files Created

| File | Purpose |
|---|---|
| `src/lib/supabase/env.ts` | Safe env accessor — `getSupabaseEnv()`, `hasSupabaseEnv()`, `getSupabaseSetupMessage()` |
| `src/lib/supabase/client.ts` | Browser-side Supabase client using public env vars |
| `src/lib/supabase/server.ts` | Server-side client via `@supabase/ssr` + Next.js cookies |
| `src/lib/supabase/admin.ts` | Service-role client — bypasses RLS, server-only |
| `src/types/database.ts` | TypeScript types for all tables + `Database` generic for `createClient<Database>` |
| `src/lib/projects.ts` | Server-side data helpers (see below) |
| `supabase/schema.sql` | Full Postgres schema with tables, indexes, RLS policies, signup trigger |
| `HANDOFF_backend-data-layer.md` | This file |

## Files Modified

| File | Change |
|---|---|
| `package.json` / `package-lock.json` | Added `@supabase/supabase-js` and `@supabase/ssr` |

No existing source files were modified.

---

## Dependencies Installed

```
@supabase/supabase-js
@supabase/ssr
```

---

## Environment Variables Required

```env
NEXT_PUBLIC_SUPABASE_URL=        # Your Supabase project URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=   # Public anon key (safe for browser)
SUPABASE_SERVICE_ROLE_KEY=       # Secret service role key — server-only, never expose to browser
OPENAI_API_KEY=                  # Already present — kept in .env.example
```

All already present in `.env.example`. Copy to `.env.local` and fill in real values from your Supabase project settings.

---

## Supabase Project Setup Steps

1. Create a project at [supabase.com](https://supabase.com) (free tier is fine for development).
2. In **Project Settings → API**, copy:
   - Project URL → `NEXT_PUBLIC_SUPABASE_URL`
   - `anon` key → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY`
3. Paste into `.env.local`.

---

## SQL Setup Instructions

1. In your Supabase project, go to **SQL Editor**.
2. Open `supabase/schema.sql` and paste the entire contents.
3. Click **Run**.
4. The script is idempotent — safe to re-run (`CREATE TABLE IF NOT EXISTS`, `DROP TRIGGER IF EXISTS`).

Alternatively, if using the Supabase CLI:
```bash
supabase link --project-ref <your-project-ref>
supabase db push
```

---

## Helper Functions in `src/lib/projects.ts`

All functions are server-side only. Each returns `{ data, error }`.

| Function | Description |
|---|---|
| `getCurrentUser()` | Returns the authenticated user id and email from the session |
| `getUserBusinesses()` | Lists all businesses owned by the current user |
| `getBusinessById(id)` | Fetches a single business by id |
| `createBusiness(input)` | Inserts a new business row |
| `getLatestBlueprintForBusiness(businessId)` | Fetches the most recent blueprint for a business |
| `saveBusinessBlueprint(input)` | Inserts a new blueprint row |
| `getHumanRequiredActions(businessId)` | Lists pending human-required actions for a business |
| `createHumanRequiredActionsFromBlueprint(businessId, userId, blueprint)` | Parses blueprint JSON and bulk-inserts human actions |
| `getAgentActivityLogs(businessId)` | Fetches activity log entries for a business |
| `createAgentActivityLog(input)` | Appends one activity log entry |
| `upsertToolPermission(input)` | Creates or updates a tool permission record (`user_id,tool_id` unique key) |

---

## What Is Intentionally Not Wired Yet

- **`/intake`** — still saves blueprint only to local state; `createBusiness` and `saveBusinessBlueprint` are not called yet.
- **`/api/generate-blueprint`** — still returns blueprint JSON without persisting to Supabase.
- **Auth UI** — no login/signup pages; `getCurrentUser()` will return an error until auth is added.
- **Dashboard UI** — no `/dashboard` page; the helpers are ready to be consumed by a future branch.
- **Middleware** — no session-refresh middleware yet; add for production auth flows.
- **`/tools`** — `upsertToolPermission` is not called from the tool registry UI yet.

---

## Lint / Build Status

Both `npm run lint` and `npm run build` pass with no errors.

---

## Recommended Next Task

**Branch: `feature/auth-ui`**

Wire up Supabase Auth:
1. Add login/signup pages (`/login`, `/signup`).
2. Add Next.js middleware (`middleware.ts`) to protect dashboard routes and refresh sessions using `createSupabaseServerClient`.
3. Connect `/intake` submit to `createBusiness` + `saveBusinessBlueprint` (requires authenticated user).
4. Build `/dashboard` using `getUserBusinesses` and related helpers.

The entire backend foundation is ready — no schema or helper changes should be needed for the basic auth+dashboard flow.
