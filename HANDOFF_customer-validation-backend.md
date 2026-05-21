# HANDOFF: Customer Validation Backend

**Branch:** `feature/customer-validation-backend`
**Author:** Arnav (AI session)
**Date:** 2026-05-21

---

## What Was Built

The customer validation module gives founders a structured workspace to discover and validate their business idea through real customer conversations. It is entirely backend/data layer — no frontend UI changes were made.

---

## Files Created

| File | Purpose |
|------|---------|
| `src/types/validation.ts` | All TypeScript types for validation entities |
| `supabase/validation.sql` | Database schema — tables, indexes, RLS |
| `src/lib/validation.ts` | Server-side helper functions (auth-gated, ownership-verified) |
| `src/app/api/businesses/[id]/validation/route.ts` | GET workspace, POST seed |
| `src/app/api/businesses/[id]/validation/personas/route.ts` | POST create, PATCH update persona |
| `src/app/api/businesses/[id]/validation/hypotheses/route.ts` | POST create, PATCH update hypothesis |
| `src/app/api/businesses/[id]/validation/leads/route.ts` | POST create, PATCH update lead |
| `src/app/api/businesses/[id]/validation/feedback/route.ts` | POST create feedback note |

---

## Files Modified

| File | Change |
|------|--------|
| `src/types/execution.ts` | Added `"validation"` to `ExecutionTimelineEvent.category` union |
| `src/lib/execution/log-categories.ts` | Added `validation_*` activity type routing to `"validation"` category |
| `src/lib/execution/status.ts` | Added 3 validation milestones + 4 validation next actions |

---

## SQL to Run

**Satvik must run `supabase/validation.sql` in the Supabase SQL Editor after merging.**

Steps:
1. Go to [supabase.com](https://supabase.com) → the bucks.ai project → SQL Editor
2. Paste the entire contents of `supabase/validation.sql`
3. Click Run
4. Verify that 4 new tables appear: `validation_personas`, `validation_hypotheses`, `validation_leads`, `validation_feedback_notes`

The SQL is idempotent (`create table if not exists`, `create index if not exists`).

---

## Database Tables

### `validation_personas`
Target customer archetypes to interview.
- Fields: `name`, `role`, `company_type`, `pain_points` (jsonb array), `goals` (jsonb array), `notes`, `priority`

### `validation_hypotheses`
Testable beliefs about market/customer/product.
- Fields: `statement`, `rationale`, `status` (untested/testing/supported/rejected/inconclusive), `evidence`

### `validation_leads`
People to contact for customer discovery.
- Fields: `name`, `company`, `role`, `contact_info`, `source`, `status`, `persona_id` (FK), `notes`, `outreach_script`

### `validation_feedback_notes`
Raw insights from customer conversations.
- Fields: `note`, `sentiment` (positive/negative/neutral), `lead_id` (FK), `persona_id` (FK), `hypothesis_id` (FK)

---

## API Routes

### Workspace
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/businesses/:id/validation` | Returns full workspace (personas, hypotheses, leads, notes, summary) |
| `POST` | `/api/businesses/:id/validation` | Body `{ action: "seed" }` — seeds from blueprint |

### Personas
| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/businesses/:id/validation/personas` | Create persona |
| `PATCH` | `/api/businesses/:id/validation/personas` | Update persona (body must include `id`) |

### Hypotheses
| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/businesses/:id/validation/hypotheses` | Create hypothesis |
| `PATCH` | `/api/businesses/:id/validation/hypotheses` | Update hypothesis (body must include `id`) |

### Leads
| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/businesses/:id/validation/leads` | Create lead |
| `PATCH` | `/api/businesses/:id/validation/leads` | Update lead (body must include `id`) |

### Feedback Notes
| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/businesses/:id/validation/feedback` | Create feedback note |

---

## Helper Functions (`src/lib/validation.ts`)

| Function | Description |
|----------|-------------|
| `getValidationWorkspace(businessId)` | Returns full workspace with computed summary |
| `seedValidationWorkspaceFromBlueprint(businessId)` | Seeds 2-3 personas, 3 hypotheses, 5 lead archetypes from blueprint |
| `createValidationPersona(input)` | Create a persona |
| `updateValidationPersona(input)` | Update a persona |
| `createValidationHypothesis(input)` | Create a hypothesis |
| `updateValidationHypothesis(input)` | Update a hypothesis |
| `createValidationLead(input)` | Create a lead (logs `validation_lead_contacted` if status is not `identified`) |
| `updateValidationLead(input)` | Update a lead (logs `validation_status_updated`) |
| `createValidationFeedbackNote(input)` | Create a feedback note (logs `validation_feedback_added`) |
| `getValidationSummary(businessId)` | Returns summary only (not full workspace) |

All functions:
- Require authenticated user
- Verify business ownership
- Return `{ data, error, code }` — never throw
- Return `code: "validation_schema_missing"` when SQL has not been applied

---

## Execution Status Changes

Three milestones added to the business execution status pipeline:
1. **Customer validation workspace created** — triggered by `validation_workspace_seeded` activity log
2. **First outreach contact added** — triggered by `validation_lead_contacted` log
3. **First feedback note recorded** — triggered by `validation_feedback_added` log

Four next actions added:
- **Set up validation workspace** — appears before workspace is seeded
- **Add first 5 leads** — appears after seeding, before first contact
- **Record first feedback note** — appears after first contact, before first feedback
- **Review validation signal** — appears after first feedback is logged

---

## How to Test

### After applying supabase/validation.sql:

**1. Logged-out returns 401**
```
GET /api/businesses/<any-id>/validation
→ 401 { ok: false, code: "unauthenticated" }
```

**2. Before SQL is applied, returns 503**
```
GET /api/businesses/<id>/validation
→ 503 { ok: false, code: "validation_schema_missing" }
```

**3. GET empty workspace (SQL applied, no data)**
```
GET /api/businesses/<id>/validation
→ 200 { ok: true, data: { summary: { canSeed: true, personaCount: 0, ... }, personas: [], ... } }
```

**4. Seed workspace from blueprint**
```
POST /api/businesses/<id>/validation
Body: { "action": "seed" }
→ 201 { ok: true, data: { seeded: true, personas: 2, hypotheses: 3, leads: 5 } }
```

**5. Add a feedback note**
```
POST /api/businesses/<id>/validation/feedback
Body: { "note": "They said pricing is fine", "sentiment": "positive" }
→ 201 { ok: true, data: { id: "...", note: "...", ... } }
```

---

## Known Limitations

1. **SQL not auto-applied** — Satvik must manually run `supabase/validation.sql`. Until then, all validation routes return `validation_schema_missing`.
2. **No PATCH for feedback notes** — Feedback notes are append-only by design. Add a `[noteId]` route if edits are needed later.
3. **No validation tab in frontend** — This is a pure backend/data layer. UI work is a separate task.
4. **Seed is one-shot** — Calling seed again appends more records. Add a guard in `getValidationWorkspace` if needed.
5. **Blueprint field extraction is best-effort** — The seeder reads common blueprint shapes but blueprint schema is untyped; fallback defaults are used when fields are missing.

---

## Next UI Task

Build a **Validation tab** in the business workspace (`src/app/dashboard/businesses/[id]/`) that:
- Calls `GET /api/businesses/:id/validation` to load the workspace
- Shows personas, hypotheses, leads, and feedback notes in compact cards
- Includes a "Seed workspace" button when `summary.canSeed === true`
- Allows updating lead status via `PATCH /api/businesses/:id/validation/leads`
- Allows logging feedback via `POST /api/businesses/:id/validation/feedback`
