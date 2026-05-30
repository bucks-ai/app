# HANDOFF: Customer Validation Node — Backend

**Branch:** `feature/customer-validation-backend`
**Author:** Arnav (AI session, 2026-05-30)
**Status:** Ready for Satvik review and SQL apply

---

## Purpose

The Customer Validation Node gives founders a structured workspace to discover
and validate their business idea through real customer conversations — before
over-investing in product or deployment.

This task builds the **data rail** (database schema, TypeScript types, server-side
helpers, and REST API routes) that the Validation Node's future agents will use.

No outreach is sent. No external tools are called. No UI is built in this task.

---

## Future Agents This Node Supports

| Agent | Responsibility (deferred) |
|-------|--------------------------|
| Persona Agent | Enrich and segment personas from blueprint or web research |
| Hypothesis Agent | Generate and auto-update hypothesis status based on feedback |
| Lead Research Agent | Discover real people matching persona segments via LinkedIn/web |
| Feedback Analysis Agent | Summarize notes, extract signal strength, tag hypotheses |
| Validation Score Agent | Compute confidence scores, derive overall validation status |

None of these agents are built in this task. The data rails (types, tables,
helper functions) they will call are ready.

---

## Files Created

| File | Purpose |
|------|---------|
| `src/types/validation.ts` | All TypeScript types for the Validation Node |
| `supabase/validation.sql` | Tables, triggers, indexes, RLS |
| `src/lib/validation.ts` | Server-side helper functions (auth-gated, typed) |
| `src/app/api/businesses/[id]/validation/route.ts` | GET workspace, POST seed |
| `src/app/api/businesses/[id]/validation/personas/route.ts` | POST create, PATCH update |
| `src/app/api/businesses/[id]/validation/hypotheses/route.ts` | POST create, PATCH update |
| `src/app/api/businesses/[id]/validation/leads/route.ts` | POST create, PATCH update |
| `src/app/api/businesses/[id]/validation/feedback/route.ts` | POST create |
| `HANDOFF_customer-validation-backend.md` | This file |

---

## Files Modified

| File | Change |
|------|--------|
| `src/types/execution.ts` | Added `"validation"` to `ExecutionTimelineEvent.category` union |
| `src/lib/execution/log-categories.ts` | Routes `validation_*` activity types to `"validation"` category |
| `src/lib/execution/status.ts` | Added 3 validation milestones + 4 validation next actions |

---

## SQL to Run (Satvik)

**After merging `feature/customer-validation-backend` into main, run
`supabase/validation.sql` in the Supabase SQL Editor.**

Steps:
1. Go to [supabase.com](https://supabase.com) → bucks.ai project → SQL Editor
2. Paste the entire contents of `supabase/validation.sql`
3. Click Run
4. Verify four new tables appear:
   - `validation_personas`
   - `validation_hypotheses`
   - `validation_leads`
   - `validation_feedback_notes`

The SQL is additive: `create table if not exists`, `create index if not exists`.
Safe to run on a live project. The RLS policies are NOT idempotent — if re-running,
drop existing policies first or wrap in a transaction.

---

## Database Tables

### `validation_personas`
Target customer archetypes.
Key fields: `name`, `segment`, `description`, `pain_points` (jsonb), `desired_outcomes` (jsonb), `channels` (jsonb), `willingness_to_pay`, `priority`, `status`

### `validation_hypotheses`
Testable beliefs about the market/customer/product.
Key fields: `title`, `description`, `type`, `assumption`, `success_criteria`, `status`, `confidence` (0–100 int), `priority`

### `validation_leads`
People to contact for customer discovery interviews.
Key fields: `name`, `company`, `role`, `segment`, `source`, `contact_url`, `email`, `status`, `notes`, `priority`

### `validation_feedback_notes`
Structured notes from customer conversations.
Key fields: `lead_id` (FK nullable), `hypothesis_id` (FK nullable), `summary`, `pain_signal`, `willingness_to_pay_signal`, `objections` (jsonb), `quotes` (jsonb), `next_step`, `signal_strength`

All tables have `updated_at` auto-stamped via a `set_updated_at()` trigger.

---

## API Routes

### Workspace
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/businesses/:id/validation` | Full workspace + summary. `canSeed: true` if empty. |
| `POST` | `/api/businesses/:id/validation` | Body: `{ "action": "seed" }` — seeds from blueprint. |

### Personas
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/validation/personas` | `name` required |
| `PATCH` | `/api/businesses/:id/validation/personas` | `id` (persona uuid) required |

### Hypotheses
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/validation/hypotheses` | `title` required |
| `PATCH` | `/api/businesses/:id/validation/hypotheses` | `id` (hypothesis uuid) required |

### Leads
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/validation/leads` | `name` required |
| `PATCH` | `/api/businesses/:id/validation/leads` | `id` (lead uuid) required |

### Feedback Notes
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/validation/feedback` | `summary` required |

All routes return:
```json
{ "ok": true,  "data": { ... } }
{ "ok": false, "code": "...", "error": "..." }
```

Error codes: `unauthenticated`, `forbidden`, `business_not_found`, `invalid_input`,
`validation_schema_missing`, `validation_create_failed`, `validation_update_failed`

---

## Helper Functions (`src/lib/validation.ts`)

| Function | Description |
|----------|-------------|
| `getValidationWorkspace(businessId)` | Full workspace with computed summary |
| `seedValidationWorkspaceFromBlueprint(businessId)` | Seeds 2 personas, 3 hypotheses, 5 leads |
| `createValidationPersona(input)` | Create + log `validation_persona_created` |
| `updateValidationPersona(input)` | Update persona |
| `createValidationHypothesis(input)` | Create + log `validation_hypothesis_created` |
| `updateValidationHypothesis(input)` | Update + log `validation_status_updated` if status changed |
| `createValidationLead(input)` | Create + log `validation_lead_created` |
| `updateValidationLead(input)` | Update + log `validation_status_updated` if status changed |
| `createValidationFeedbackNote(input)` | Create + log `validation_feedback_added` |
| `getValidationSummary(businessId)` | Summary only (lighter than full workspace) |

All functions: auth-required, ownership-verified, return `{data, error, code}`,
return `code: "validation_schema_missing"` when SQL not applied.

---

## Activity Log Events Added

| Activity type | When |
|---------------|------|
| `validation_workspace_seeded` | Seed action completes |
| `validation_persona_created` | Any persona created |
| `validation_hypothesis_created` | Any hypothesis created |
| `validation_lead_created` | Any lead created |
| `validation_feedback_added` | Any feedback note created |
| `validation_status_updated` | Hypothesis or lead status changes |

---

## Execution Status Changes

Three milestones added:
1. **Customer validation workspace created** — `validation_workspace_seeded` log
2. **First validation lead added** — `validation_lead_created` log
3. **First feedback note recorded** — `validation_feedback_added` log

Four next actions added (appear conditionally based on workspace state):
- Set up validation workspace
- Add first 5 customer leads
- Record first interview feedback
- Review validation signal

---

## Manual Test Plan

### Before SQL is applied:
```
GET  /api/businesses/<id>/validation          → 503 { code: "validation_schema_missing" }
POST /api/businesses/<id>/validation/feedback → 503 { code: "validation_schema_missing" }
```

### After SQL is applied:
```
# 1. Logged-out user
GET /api/businesses/<id>/validation           → 401 { code: "unauthenticated" }

# 2. Empty workspace (fresh business)
GET /api/businesses/<id>/validation           → 200 { data: { summary: { canSeed: true, ... } } }

# 3. Seed workspace
POST /api/businesses/<id>/validation
Body: { "action": "seed" }                   → 201 { data: { seeded: true, personas: 2, hypotheses: 3, leads: 5 } }

# 4. Get workspace after seed
GET /api/businesses/<id>/validation           → 200 { data: { personas: [...], hypotheses: [...], ... } }

# 5. Add lead
POST /api/businesses/<id>/validation/leads
Body: { "name": "Alice Chen", "company": "Stripe", "role": "Eng Manager" }
                                              → 201 { data: { id: "...", name: "Alice Chen", ... } }

# 6. Update lead status
PATCH /api/businesses/<id>/validation/leads
Body: { "id": "<lead-uuid>", "status": "contacted" }
                                              → 200 { data: { status: "contacted", ... } }

# 7. Add feedback note
POST /api/businesses/<id>/validation/feedback
Body: {
  "summary": "Pain is real but budget is tight",
  "signal_strength": "medium",
  "pain_signal": "Confirmed — wastes 3hrs/week",
  "willingness_to_pay_signal": "Would pay up to $50/mo",
  "quotes": ["This is the thing I hate most about my job"]
}                                             → 201 { data: { id: "...", signal_strength: "medium", ... } }
```

### What could not be manually tested (SQL not applied locally):
- Actual Supabase queries against the four new tables
- RLS enforcement
- `updated_at` trigger behaviour
- Seeded data accuracy against a real blueprint JSON

---

## Known Limitations

1. **SQL must be applied manually** — Satvik applies `supabase/validation.sql` after merge.
2. **Feedback notes are append-only** — No PATCH on feedback; intended by design (audit trail).
3. **No UI** — This is purely backend/data. Validation tab is a separate UI task.
4. **Seed is not idempotent** — Calling seed twice appends more records. Guard in UI.
5. **Blueprint extraction is best-effort** — Blueprint JSON is untyped; falls back to generic defaults if fields are missing.
6. **No outreach or external tool calls** — Deliberately excluded; Lead Research Agent handles this later.
7. **confidence is a manual field** — Validation Score Agent will compute it automatically in future.

---

## What Is Intentionally Deferred

- Agent Registry entries for Persona / Hypothesis / Lead Research / Feedback Analysis / Validation Score agents
- Outreach script generation or email sending
- Lead enrichment via LinkedIn or web search
- Automated confidence score computation
- Feedback summarisation (Feedback Analysis Agent)
- Customer Validation tab UI
- Validation report / export

---

## Next UI Task

Build a **Customer Validation tab** inside the business workspace
(`src/app/dashboard/businesses/[id]/`) that:

- Calls `GET /api/businesses/:id/validation` to load the workspace
- Shows `canSeed` prompt with a "Seed workspace" button when empty
- Renders personas, hypotheses, leads, and feedback notes in compact cards
- Allows lead status updates via `PATCH /api/businesses/:id/validation/leads`
- Allows adding feedback notes via `POST /api/businesses/:id/validation/feedback`
- Surfaces `summary.strongSignalCount` and `summary.status` as a progress indicator
