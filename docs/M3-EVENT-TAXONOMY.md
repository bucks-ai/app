# M3: Canonical Analytics Event Taxonomy

Source of truth: `src/lib/analytics/events.ts` (`ANALYTICS_EVENTS`). This
document explains the funnel these events model and the conventions every
future `posthog.capture()` call must follow. This task defines the catalog
only — no capture calls are wired up yet.

## Funnel order

The eleven canonical events map onto seven funnel stages, in this order:

```
signup -> intake -> blueprint -> saved -> tool_approved -> repo -> deploy
```

| Stage | Event(s) | business_id exists? |
|---|---|---|
| `signup` | `user_signed_up` | no |
| `intake` | `intake_started`, `intake_submitted` | no |
| `blueprint` | `blueprint_generated` | no |
| `saved` | `blueprint_saved` | **yes — created here** |
| `tool_approved` | `tool_approval_requested`, `tool_approved` | yes |
| `repo` | `repo_created`, `scaffold_prepared` | yes |
| `deploy` | `vercel_project_created`, `deploy_succeeded` | yes |

`blueprint_saved` is the pivot point: it's the moment the business record is
persisted (`/api/businesses/save-blueprint`), so it's the first event in the
funnel that carries a `business_id`. Every event from `blueprint_saved`
onward requires one.

## Property conventions

- **`business_id` where applicable.** Any event fired after a business
  record exists must include `business_id` in its properties, matching the
  `business_id` column used elsewhere in the schema (e.g.
  `agent_activity_logs`, `validation_leads`). Events fired before the
  business exists (`user_signed_up` through `blueprint_generated`) have no
  `business_id` requirement.
- **Never email or other PII in properties.** Identify people via
  PostHog's `distinct_id` (set at auth) and businesses via `business_id`.
  Do not put email, name, phone, or address into event properties.
  `FORBIDDEN_PROPERTY_KEYS` in `events.ts` enumerates keys that must never
  appear, and is asserted against in the test suite so the catalog itself
  can't declare one as required.
- **snake_case names.** Every event name matches `^[a-z][a-z0-9]*(_[a-z0-9]+)*$`
  — enforced by `src/lib/analytics/events.test.ts`.
- **Frozen catalog.** `ANALYTICS_EVENTS`, `ALL_ANALYTICS_EVENTS`, each event
  definition, and each `requiredProperties` array are all frozen with
  `Object.freeze` so the taxonomy can't be mutated at runtime by whatever
  code eventually imports it.

## Event reference

| Event name | Description | Required properties |
|---|---|---|
| `user_signed_up` | A visitor completes account creation and becomes an authenticated user. | `signup_method` |
| `intake_started` | A user begins the founder intake wizard for a new business idea. | — |
| `intake_submitted` | A user submits the completed intake wizard, ready for blueprint generation. | — |
| `blueprint_generated` | The AI pipeline returns a generated launch blueprint from intake data. | — |
| `blueprint_saved` | The founder approves the blueprint and it is persisted, creating the business record. | `business_id` |
| `tool_approval_requested` | A tool permission (e.g. GitHub, Vercel) enters the queue awaiting founder approval. | `business_id` |
| `tool_approved` | The founder approves a pending tool permission. | `business_id` |
| `repo_created` | A GitHub repository is provisioned for the business. | `business_id` |
| `scaffold_prepared` | A deployable Next.js scaffold is written to the business repository. | `business_id` |
| `vercel_project_created` | A Vercel project is created and linked to the business repository. | `business_id` |
| `deploy_succeeded` | A deployment for the business completes successfully and is publicly reachable. | `business_id` |

## `user_signed_up` capture point

`user_signed_up` is captured **server-side only**, once, in
`POST /api/auth/signup` (`src/app/api/auth/signup/route.ts`) — the route the
signup form now submits to instead of calling `supabase.auth.signUp()`
directly from the browser. This is the single reliable point where a new
account first exists:

- The route calls `supabase.auth.signUp()` through the request-bound SSR
  client, so the resulting session cookie (if "Confirm email" is off) is set
  directly on the response.
- It only fires `capture("USER_SIGNED_UP", ...)` when Supabase's response
  indicates an account was actually created (`user.identities` non-empty).
  A `signUp()` call for an already-registered, confirmed email returns an
  obfuscated user with no identities and no error — no event fires for that
  case, so re-submitting the signup form for an existing account can't
  double-count as a new signup.
- Every call includes `signup_method: "email"` — the only signup path this
  app supports today. A future OAuth/social signup path must use the same
  route (or otherwise dedupe through this one) and pass its own
  `signup_method` value rather than adding a second, parallel capture point.

There is deliberately no client-side capture of `user_signed_up`: pick one
authoritative source (server, since it's the only place that can tell a real
signup from a duplicate) and never fire both.

## Test-traffic guard

Source of truth: `src/lib/analytics/guard.ts` (`guardCapture`). Both capture
helpers — `src/lib/analytics/server.ts` (server-side) and
`src/lib/analytics/client.ts` (client-side, used by `PostHogProvider` for
`$pageview` and available to any future client capture point) — run every
call through this guard before sending anything to PostHog, so no capture
point can forget it.

**When capture is dropped.** A capture call is a complete no-op (no
network call, no PostHog client construction) whenever the traffic is
E2E or seeded-test traffic:

- `E2E_FAKE_AI=true` (see `src/lib/e2e-fake-ai.ts`), or its client-bundle
  mirror `NEXT_PUBLIC_E2E_FAKE_AI=true` — Next.js only inlines
  `NEXT_PUBLIC_`-prefixed vars into the browser, so the mirror is what lets
  the guard also suppress client-side capture during an E2E run.
- The authenticated user's email equals `TEST_USER_EMAIL` (the dedicated
  seeded E2E/QA account — see `scripts/seed-e2e.ts`).

**`M3_VERIFY=true` override.** An explicit, opt-in override (plus its
client-bundle mirror `NEXT_PUBLIC_M3_VERIFY=true`) that re-enables capture
for test traffic and stamps **every** captured event — test traffic or
not — with `verification_run: true`. This lets a one-off E2E run be
verified end-to-end against real PostHog data without polluting the
regular funnel dashboards, since every event from that run carries the
marker. Intended to be used once, by the m3-10 task, to confirm the
funnel fires correctly; it is not meant to run continuously in CI.

## Non-goals

None of the tasks that built up this document (catalog definition,
server-side capture wiring, the test-traffic guard above) touch:

- Runner (`runner/langgraph/`) code or its dependencies.
- Stage-transition or funnel-completion metrics — that's future analytics
  work built on top of the capture calls that now exist.
