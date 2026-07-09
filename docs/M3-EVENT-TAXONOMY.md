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
| `user_signed_up` | A visitor completes account creation and becomes an authenticated user. | — |
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

## Non-goals of this task

This task only defines the catalog and its conventions. It does **not**:

- Add any `posthog.capture()` calls at existing call sites.
- Change runner (`runner/langgraph/`) code or add dependencies.
- Define stage-transition or funnel-completion metrics — that's future
  analytics work once capture calls exist.
