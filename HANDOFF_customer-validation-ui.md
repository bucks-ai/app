# HANDOFF: Customer Validation UI

**Branch:** `feature/customer-validation-ui`
**Status:** Built for validation against the merged backend

## Purpose

Adds a compact Customer Validation tab to the business workspace so founders can
seed a validation workspace, review personas and hypotheses, manage interview
leads, and record customer feedback.

No Research Mode, Agent Registry, outreach automation, Vercel automation, GitHub
automation, or Supabase SQL execution was added.

## Files Created

| File | Purpose |
|------|---------|
| `src/lib/validation-client.ts` | Client-side fetch helper for validation API routes with friendly errors |
| `src/types/validation-ui.ts` | UI-safe validation input/result types |
| `src/components/validation/ValidationWorkspacePanel.tsx` | Main validation workspace loader and renderer |
| `src/components/validation/ValidationSummaryHeader.tsx` | Compact counts, status, and next validation action |
| `src/components/validation/ValidationEmptyState.tsx` | Seed CTA for empty validation workspaces |
| `src/components/validation/PersonaList.tsx` | Compact persona cards |
| `src/components/validation/HypothesisTracker.tsx` | Hypothesis list with status updates |
| `src/components/validation/LeadPipeline.tsx` | Lead pipeline grouped by status with add/update controls |
| `src/components/validation/FeedbackNotes.tsx` | Feedback list with add feedback form |
| `src/components/validation/ValidationNextActionCard.tsx` | Validation next-action resolver/card |
| `src/components/validation/ValidationStatusBadge.tsx` | Small status/priority/signal badge |
| `src/components/validation/ValidationOverviewCard.tsx` | Compact overview validation summary |
| `src/components/validation/ValidationRailCard.tsx` | Compact right-rail validation summary |
| `src/components/workspace/tabs/ValidationTab.tsx` | Workspace tab wrapper |
| `HANDOFF_customer-validation-ui.md` | This handoff |

## Files Modified

| File | Change |
|------|--------|
| `src/components/workspace/WorkspaceTabs.tsx` | Added `Validation` tab between Deploy and Tools |
| `src/components/workspace/BusinessWorkspace.tsx` | Added Validation tab routing and rendering |
| `src/components/workspace/tabs/OverviewTab.tsx` | Added compact validation summary card |
| `src/components/workspace/WorkspaceRightRail.tsx` | Added compact Validation card |
| `src/components/workspace/next-action.ts` | Routes validation next actions to the Validation tab |

## Components Added

- `ValidationWorkspacePanel`
- `ValidationSummaryHeader`
- `ValidationEmptyState`
- `PersonaList`
- `HypothesisTracker`
- `LeadPipeline`
- `FeedbackNotes`
- `ValidationNextActionCard`
- `ValidationStatusBadge`
- `ValidationOverviewCard`
- `ValidationRailCard`
- `ValidationTab`

## API Routes Consumed

- `GET /api/businesses/[id]/validation`
- `POST /api/businesses/[id]/validation`
- `POST /api/businesses/[id]/validation/personas`
- `PATCH /api/businesses/[id]/validation/personas`
- `POST /api/businesses/[id]/validation/hypotheses`
- `PATCH /api/businesses/[id]/validation/hypotheses`
- `POST /api/businesses/[id]/validation/leads`
- `PATCH /api/businesses/[id]/validation/leads`
- `POST /api/businesses/[id]/validation/feedback`

## UI States Handled

- Loading workspace
- Empty workspace with seed CTA
- Seed in progress and seed failure
- Backend unavailable
- Validation schema missing
- Unauthenticated user
- Network error
- Create/update failures for leads, hypotheses, and feedback
- Workspace with no personas, hypotheses, leads, or feedback

## Manual QA Plan

1. Open `/dashboard` and confirm saved business cards still render.
2. Open a business detail page and confirm the tab bar includes Validation.
3. Open the Validation tab and confirm the workspace loads.
4. For an empty workspace, click Create validation workspace and confirm seeded personas, hypotheses, and leads render.
5. Add a lead and confirm it appears in the Identified column.
6. Change a lead status and confirm it moves columns after reload.
7. Change a hypothesis status and confirm the badge updates after reload.
8. Add feedback with and without a lead or hypothesis link.
9. Resize to 390px and confirm the tab bar scrolls, forms stack, and no horizontal overflow appears.

## Known Limitations

- Feedback is append-only because the backend exposes create only.
- Persona creation/editing is exposed in the client helper but not surfaced as a form in this compact UI.
- Overview and right rail fetch the full validation workspace because no summary-only API route exists.
- Seed is controlled by the backend and may append duplicates if called repeatedly outside the UI.

## Intentionally Deferred

- Research Mode
- Agent Registry
- Automated lead research
- Outreach sending
- Feedback analysis agent
- Validation score agent
- Supabase SQL application
