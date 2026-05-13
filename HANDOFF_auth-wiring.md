# Handoff: auth-wiring

Branch: `feature/wire-supabase-auth`
Date: 2026-05-12

---

## Auth approach chosen

**Client-side Supabase auth with `createBrowserClient`** for login and signup pages.

Both `/login` and `/signup` are already `"use client"` components. Using the browser Supabase client (`createBrowserClient` from `src/lib/supabase/client.ts`) keeps the implementation simple and avoids the complexity of Server Actions + `useActionState` for this MVP stage.

Middleware uses `createServerClient` from `@supabase/ssr` to refresh session cookies on every request, which is the recommended pattern for Next.js App Router per the `@supabase/ssr` README.

---

## Files created

| File | Purpose |
|---|---|
| `src/components/auth/LogoutButton.tsx` | Client component — calls `supabase.auth.signOut()`, redirects to `/login` |
| `src/lib/auth.ts` | Server-side helpers: `getAuthenticatedUser()`, `requireAuthenticatedUser()` |
| `middleware.ts` | Session cookie refresh on every request via `@supabase/ssr` |
| `HANDOFF_auth-wiring.md` | This file |

---

## Files modified

| File | Change |
|---|---|
| `src/app/login/page.tsx` | Wired to real Supabase `signInWithPassword`; redirects to `/dashboard` on success; shows inline error on failure; shows env setup message when Supabase is not configured |
| `src/app/signup/page.tsx` | Wired to real Supabase `signUp`; handles email-confirmation and immediate-session cases; shows inline errors; shows env setup message when Supabase is not configured |
| `src/components/shared/Navbar.tsx` | Converted to `"use client"` — reads auth state via `onAuthStateChange` and conditionally renders Dashboard link + LogoutButton vs Sign in link |

---

## Environment variables required

```env
NEXT_PUBLIC_SUPABASE_URL=       # Your Supabase project URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=  # Public anon key — safe for browser
```

`SUPABASE_SERVICE_ROLE_KEY` is NOT required for auth flows. Login and signup only use the anon key.

If either public variable is missing, the app will:
- Show a developer setup panel on `/login` and `/signup` instead of crashing.
- The build will still succeed.
- Middleware will pass through all requests without touching cookies.

---

## How to test signup

1. Run `npm run dev`.
2. Go to `http://localhost:3000/signup`.
3. Fill in a valid email and matching passwords.
4. Submit.
5. If Supabase email confirmation is **enabled** (default): you will see a green confirmation message. Check the email inbox for the confirmation link.
6. If Supabase email confirmation is **disabled** (Supabase Dashboard → Auth → Email → "Confirm email" toggle off): you will be redirected directly to `/dashboard`.

To disable email confirmation for local testing: Supabase Dashboard → Authentication → Providers → Email → uncheck "Confirm email".

---

## How to test login

1. Sign up first (or create a user in the Supabase Dashboard → Authentication → Users).
2. Go to `http://localhost:3000/login`.
3. Enter valid credentials and submit.
4. You should be redirected to `/dashboard`.
5. Enter wrong credentials — you should see an inline red error message.

---

## How to test logout

1. Sign in so you have an active session.
2. In the Navbar, "Sign out" will appear where "Sign in" was.
3. Click "Sign out".
4. You should be redirected to `/login`.
5. The Navbar should show "Sign in" again.

Alternatively, import `<LogoutButton />` from `src/components/auth/LogoutButton.tsx` anywhere in the dashboard layout and test from there.

---

## Known limitations

- **Navbar auth state flickers on initial load.** The `isAuthenticated` state starts as `null` (renders nothing in place of the auth link) until `getSession()` resolves. This is inherent to a client-side auth check and is acceptable for MVP.
- **Dashboard is not protected yet.** `/dashboard` is still publicly accessible. The `requireAuthenticatedUser()` helper in `src/lib/auth.ts` is ready to be used but was not added to the dashboard pages per the task instructions ("do not hard-protect /dashboard in this branch").
- **No OAuth providers.** Only email/password auth is wired.
- **No password reset flow.**

---

## What is intentionally deferred

- Hard-protecting `/dashboard` — deferred to the next integration branch to avoid conflicts with the project-persistence branch.
- Wiring `requireAuthenticatedUser()` into dashboard pages.
- Connecting `/intake` submit to `createBusiness` + `saveBusinessBlueprint` for authenticated users.
- OAuth (GitHub, Google) — deferred per project scope.
- Password reset / magic link flows.
- Navbar SSR auth state — currently client-side only to stay compatible with the `"use client"` pages that import it.

---

## Recommended next task

**Branch: `feature/dashboard-persistence`**

1. Call `requireAuthenticatedUser()` at the top of `src/app/dashboard/page.tsx` to gate the dashboard.
2. Replace `src/components/dashboard/mock-data.ts` with real Supabase queries using the helpers in `src/lib/projects.ts`.
3. Connect the `/intake` form submit to `createBusiness` + `saveBusinessBlueprint` for the authenticated user.
4. Add the `LogoutButton` to the dashboard sidebar/header.

---

## Lint / build status

- `npm run lint`: **passed** (0 errors, 0 warnings)
- `npm run build`: **passed** — all 13 pages compiled and generated successfully
- Pre-existing workspace-root warning about multiple lockfiles is unchanged from previous branches and does not affect build output.
