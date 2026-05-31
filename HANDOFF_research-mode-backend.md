# HANDOFF: Research Node — Backend

**Branch:** `feature/research-mode-backend`
**Author:** Arnav (AI session, 2026-05-31)
**Status:** Ready for SQL apply and merge

---

## Purpose

The Research Node gives founders a structured workspace to map the business
opportunity before overbuilding — capturing segments, competitors, budget
signals, monetization assumptions, distribution channels, risks, and testable
hypotheses, all driven by blueprint fields or founder input.

This task builds the **data rail** (database schema, TypeScript types, server-side
helpers, and REST API routes) that the Research Node's future agents will use.

No external web browsing is performed. No outreach is sent. No UI is built.
Seeded data is derived deterministically from blueprint fields and documented
placeholder copy.

---

## Future Agents This Node Supports

| Agent | Responsibility (deferred) |
|-------|--------------------------|
| Market Research Agent | Enriches the workspace with web research, trend data, and market reports |
| Customer Segment Agent | Discovers and validates customer segments via surveys, forums, or social signals |
| Competitor Agent | Deep-dives competitor pricing, positioning, and weaknesses |
| Monetization Agent | Stress-tests pricing assumptions against real comp data |
| Distribution Agent | Scores and ranks channels against competitive data |
| Risk Agent | Cross-references risks against industry failure patterns |
| Opportunity Scoring Agent | Computes and updates `opportunity_score` on the research report |

None of these agents are built in this task. The data rails they will call are ready.

---

## Files Created

| File | Purpose |
|------|---------|
| `src/types/research.ts` | All TypeScript types for the Research Node |
| `supabase/research.sql` | 9 tables, triggers, indexes, RLS |
| `src/lib/research.ts` | Server-side helper functions (auth-gated, typed) |
| `src/app/api/businesses/[id]/research/route.ts` | GET workspace, POST generate |
| `src/app/api/businesses/[id]/research/segments/route.ts` | POST create, PATCH update |
| `src/app/api/businesses/[id]/research/buyer-budgets/route.ts` | POST create, PATCH update |
| `src/app/api/businesses/[id]/research/competitors/route.ts` | POST create, PATCH update |
| `src/app/api/businesses/[id]/research/monetization/route.ts` | POST create, PATCH update |
| `src/app/api/businesses/[id]/research/distribution/route.ts` | POST create, PATCH update |
| `src/app/api/businesses/[id]/research/risks/route.ts` | POST create, PATCH update |
| `src/app/api/businesses/[id]/research/hypotheses/route.ts` | POST create, PATCH update |
| `src/app/api/businesses/[id]/research/evidence/route.ts` | POST create (append-only) |
| `HANDOFF_research-mode-backend.md` | This file |

---

## Files Modified

| File | Change |
|------|--------|
| `src/types/execution.ts` | Added `"research"` to `ExecutionTimelineEvent.category` union |
| `src/lib/execution/log-categories.ts` | Routes `research_*` activity types to `"research"` category |
| `src/lib/execution/status.ts` | Added 3 research milestones + 4 research next actions + `phaseByMilestone` entries |

---

## SQL to Run (Satvik)

**After merging `feature/research-mode-backend` into main, run
`supabase/research.sql` in the Supabase SQL Editor.**

Steps:
1. Go to [supabase.com](https://supabase.com) → bucks.ai project → SQL Editor
2. Paste the entire contents of `supabase/research.sql`
3. Click Run
4. Verify nine new tables appear:
   - `research_reports`
   - `research_customer_segments`
   - `research_buyer_budgets`
   - `research_competitors`
   - `research_monetization_models`
   - `research_distribution_channels`
   - `research_risks`
   - `research_hypotheses`
   - `research_evidence`

**Note on `set_updated_at()` trigger:** `research.sql` assumes `validation.sql`
has already been applied (the trigger function is created there). If running in
isolation, uncomment the `set_updated_at()` block at the top of `research.sql`.

The SQL is additive: `create table if not exists`, `create index if not exists`.
Safe to run on a live project. The RLS policies are NOT idempotent — if re-running,
drop existing policies first or wrap in a transaction.

---

## Database Tables

### `research_reports`
Top-level opportunity thesis. One per business (most recent is active).
Key fields: `title`, `status`, `opportunity_score` (0–100 int), `thesis`, `target_customer`, `money_pool`, `wedge`, `recommendation`, `summary`, `confidence`, `priority`

### `research_customer_segments`
Target customer archetypes identified during research.
Key fields: `name`, `description`, `pain_level` (0–10), `ability_to_pay` (0–10), `reachability` (0–10), `market_size_guess`, `channels` (jsonb), `evidence_summary`, `confidence`, `priority`

### `research_buyer_budgets`
Budget and willingness-to-pay analysis per buyer archetype.
Key fields: `buyer`, `budget_owner`, `existing_spend`, `willingness_to_pay`, `value_driver`, `pricing_signal`, `confidence`, `priority`

### `research_competitors`
Competitive landscape map.
Key fields: `name`, `url`, `category`, `positioning`, `pricing_summary`, `strengths` (jsonb), `weaknesses` (jsonb), `wedge_opportunity`, `confidence`, `priority`

### `research_monetization_models`
Revenue model assumptions.
Key fields: `model`, `buyer`, `price_assumption`, `value_metric`, `reasoning`, `confidence`, `priority`

### `research_distribution_channels`
Acquisition channel analysis with scored attributes.
Key fields: `channel`, `description`, `speed_score` (0–10), `cost_score` (0–10), `difficulty_score` (0–10), `reasoning`, `confidence`, `priority`

### `research_risks`
Risks to the opportunity.
Key fields: `title`, `description`, `severity` (critical/high/medium/low), `mitigation`, `confidence`, `priority`

### `research_hypotheses`
Research-phase testable beliefs (distinct from Customer Validation hypotheses).
Key fields: `title`, `description`, `test_method`, `success_criteria`, `confidence`, `priority`

### `research_evidence`
Evidence items supporting findings. Append-only by design.
Key fields: `claim`, `source`, `source_url`, `evidence_type`, `confidence`, `notes`

All tables have `updated_at` auto-stamped via a `set_updated_at()` trigger.

---

## API Routes

### Research Workspace
| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/businesses/:id/research` | Full workspace + summary. `canGenerate: true` if empty. |
| `POST` | `/api/businesses/:id/research` | Body: `{ "action": "generate" }` — generates from blueprint. |

### Customer Segments
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/research/segments` | `name` required |
| `PATCH` | `/api/businesses/:id/research/segments` | `id` (segment uuid) required |

### Buyer Budgets
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/research/buyer-budgets` | `buyer` required |
| `PATCH` | `/api/businesses/:id/research/buyer-budgets` | `id` (record uuid) required |

### Competitors
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/research/competitors` | `name` required |
| `PATCH` | `/api/businesses/:id/research/competitors` | `id` (competitor uuid) required |

### Monetization Models
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/research/monetization` | `model` required |
| `PATCH` | `/api/businesses/:id/research/monetization` | `id` (model uuid) required |

### Distribution Channels
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/research/distribution` | `channel` required |
| `PATCH` | `/api/businesses/:id/research/distribution` | `id` (channel uuid) required |

### Risks
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/research/risks` | `title` required |
| `PATCH` | `/api/businesses/:id/research/risks` | `id` (risk uuid) required |

### Research Hypotheses
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/research/hypotheses` | `title` required |
| `PATCH` | `/api/businesses/:id/research/hypotheses` | `id` (hypothesis uuid) required |

### Evidence
| Method | URL | Body required |
|--------|-----|---------------|
| `POST` | `/api/businesses/:id/research/evidence` | `claim` required |

All routes return:
```json
{ "ok": true,  "data": { ... } }
{ "ok": false, "code": "...", "error": "..." }
```

Error codes: `unauthenticated`, `forbidden`, `business_not_found`, `invalid_input`,
`research_schema_missing`, `research_create_failed`, `research_update_failed`,
`research_generate_failed`

---

## Helper Functions (`src/lib/research.ts`)

| Function | Description |
|----------|-------------|
| `getResearchWorkspace(businessId)` | Full workspace with computed summary |
| `generateResearchWorkspaceFromBlueprint(businessId)` | Seeds 1 report, 3 segments, 2 buyer budgets, 3 competitors, 2 monetization models, 3 channels, 3 risks, 3 hypotheses, 3 evidence records |
| `createResearchReport(input)` | Create + log `research_report_created` |
| `updateResearchReport(input)` | Update + log `research_status_updated` if status changed |
| `createResearchCustomerSegment(input)` | Create + log `research_segment_created` |
| `updateResearchCustomerSegment(input)` | Update segment |
| `createResearchBuyerBudget(input)` | Create + log `research_buyer_budget_created` |
| `updateResearchBuyerBudget(input)` | Update buyer budget record |
| `createResearchCompetitor(input)` | Create + log `research_competitor_created` |
| `updateResearchCompetitor(input)` | Update competitor |
| `createResearchMonetizationModel(input)` | Create + log `research_monetization_created` |
| `updateResearchMonetizationModel(input)` | Update monetization model |
| `createResearchDistributionChannel(input)` | Create + log `research_distribution_created` |
| `updateResearchDistributionChannel(input)` | Update distribution channel |
| `createResearchRisk(input)` | Create + log `research_risk_created` |
| `updateResearchRisk(input)` | Update risk |
| `createResearchHypothesis(input)` | Create + log `research_hypothesis_created` |
| `updateResearchHypothesis(input)` | Update + log `research_status_updated` if confidence changed |
| `createResearchEvidence(input)` | Create + log `research_evidence_created` |
| `getResearchSummary(businessId)` | Summary only (lighter than full workspace) |

All functions: auth-required, ownership-verified, return `{data, error, code}`,
return `code: "research_schema_missing"` when SQL not applied.

---

## Activity Log Events Added

| Activity type | When |
|---------------|------|
| `research_workspace_generated` | Generate action completes |
| `research_report_created` | Any report created manually |
| `research_segment_created` | Any segment created |
| `research_buyer_budget_created` | Any buyer budget record created |
| `research_competitor_created` | Any competitor created |
| `research_monetization_created` | Any monetization model created |
| `research_distribution_created` | Any distribution channel created |
| `research_risk_created` | Any risk created |
| `research_hypothesis_created` | Any research hypothesis created |
| `research_evidence_created` | Any evidence record created |
| `research_status_updated` | Report status or hypothesis confidence changes |

---

## Execution Status Changes

Three milestones added:
1. **Research workspace generated** — `research_workspace_generated` log
2. **Opportunity score created** — `research_report_created` log
3. **First research hypothesis created** — `research_hypothesis_created` log

Four next actions added (appear conditionally):
- Run research mode (when workspace not yet generated)
- Review opportunity score (when workspace exists but no report yet)
- Validate highest-risk assumption (when workspace exists but no hypothesis)
- Move research hypotheses to validation (when at least one hypothesis exists)

`"research"` added to `ExecutionTimelineEvent.category` union in `src/types/execution.ts`.

---

## Manual Test Plan

### Before SQL is applied:
```
GET  /api/businesses/<id>/research          → 503 { code: "research_schema_missing" }
POST /api/businesses/<id>/research/risks    → 503 { code: "research_schema_missing" }
```

### After SQL is applied:
```
# 1. Logged-out user
GET /api/businesses/<id>/research           → 401 { code: "unauthenticated" }

# 2. Empty workspace
GET /api/businesses/<id>/research           → 200 { data: { summary: { canGenerate: true, ... } } }

# 3. Generate workspace
POST /api/businesses/<id>/research
Body: { "action": "generate" }              → 201 { data: { generated: true, segments: 3, competitors: 3, ... } }

# 4. Get workspace after generate
GET /api/businesses/<id>/research           → 200 { data: { report: {...}, segments: [...], ... } }

# 5. Add a competitor
POST /api/businesses/<id>/research/competitors
Body: { "name": "Notion", "category": "indirect", "pricing_summary": "$8/mo" }
                                            → 201 { data: { id: "...", name: "Notion", ... } }

# 6. Update competitor
PATCH /api/businesses/<id>/research/competitors
Body: { "id": "<uuid>", "wedge_opportunity": "AI-native workflows Notion can't support" }
                                            → 200 { data: { wedge_opportunity: "...", ... } }

# 7. Add evidence
POST /api/businesses/<id>/research/evidence
Body: {
  "claim": "SMB ops teams spend 8hrs/week on manual reporting",
  "source": "G2 survey 2025",
  "evidence_type": "data_point",
  "confidence": "weak_signal"
}                                           → 201 { data: { id: "...", claim: "...", ... } }
```

### What could not be manually tested (SQL not applied locally):
- Actual Supabase queries against the nine new tables
- RLS enforcement
- `updated_at` trigger behaviour
- Seeded data accuracy against a real blueprint JSON
- `opportunity_score` integer constraint validation

---

## Known Limitations

1. **SQL must be applied manually** — Satvik applies `supabase/research.sql` after merge.
2. **`set_updated_at()` trigger dependency** — `research.sql` assumes `validation.sql` was applied first. Uncomment the trigger function block if running in isolation.
3. **Generation is deterministic, not AI-powered** — `generateResearchWorkspaceFromBlueprint` derives content from blueprint fields and uses sensible placeholder copy. The Market Research Agent (future) will replace this with real web research.
4. **Evidence is append-only** — No PATCH on evidence; intended for audit trail integrity.
5. **No UI** — This is purely backend/data. Research tab is a separate UI task.
6. **Generate is not idempotent** — Calling generate twice appends more records. Guard in UI.
7. **Blueprint extraction is best-effort** — Blueprint JSON is untyped; falls back to generic defaults if fields are missing.
8. **No external tool calls** — Deliberately excluded; Research Node agents handle web research later.
9. **`opportunity_score` is a manual field** — Opportunity Scoring Agent will compute it automatically in future.

---

## What Is Intentionally Deferred

- Agent Registry entries for Market Research / Competitor / Monetization / Distribution / Risk / Opportunity Scoring agents
- Real web research, scraping, or AI-generated content in `generateResearchWorkspaceFromBlueprint`
- Automated `opportunity_score` computation
- Competitor enrichment via LinkedIn, G2, or Crunchbase
- Research report export or PDF
- Research Node UI tab
- Linking `research_hypotheses` → `validation_hypotheses` promotion flow

---

## Next UI Task

Build a **Research tab** inside the business workspace
(`src/app/dashboard/businesses/[id]/`) that:

- Calls `GET /api/businesses/:id/research` to load the workspace
- Shows `canGenerate` prompt with a "Generate research" button when empty
- Renders report (thesis, opportunity score, wedge) as a header card
- Renders segments, competitors, risks, and hypotheses in scrollable sections
- Allows updating competitors and risks via `PATCH`
- Allows adding evidence via `POST /api/businesses/:id/research/evidence`
- Surfaces `summary.opportunityScore` and `summary.status` as progress indicators
