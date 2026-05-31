# HANDOFF: Research Mode UI

**Branch:** `feature/research-mode-ui`
**Status:** Built for validation against the merged Research Mode backend

## Purpose

Adds a compact Research tab to the business workspace so founders can review
where the money is in a business idea before overbuilding. The UI consumes the
merged Research Mode backend and renders opportunity thesis, customer segments,
buyer budgets, competitors, monetization models, distribution channels, risks,
hypotheses, evidence, and a next research action.

No Supabase SQL was applied automatically. No Agent Registry, Agent Runs,
deployment automation, GitHub automation, or Vercel automation was added.

## Files Created

| File | Purpose |
|------|---------|
| `src/lib/research-client.ts` | Client-side fetch helper for Research API routes with friendly errors |
| `src/types/research-ui.ts` | UI-safe Research result and input types |
| `src/components/research/ResearchWorkspacePanel.tsx` | Main research workspace loader and renderer |
| `src/components/research/ResearchEmptyState.tsx` | Generate CTA for empty research workspaces |
| `src/components/research/OpportunityScoreCard.tsx` | Opportunity score, thesis, target customer, money pool, wedge, recommendation |
| `src/components/research/ResearchSummaryHeader.tsx` | Compact status, counts, opportunity score, and next action |
| `src/components/research/CustomerSegmentsPanel.tsx` | Customer segment cards |
| `src/components/research/BuyerBudgetPanel.tsx` | Buyer and budget analysis cards |
| `src/components/research/CompetitorMapPanel.tsx` | Competitor map cards |
| `src/components/research/MonetizationPanel.tsx` | Monetization model cards |
| `src/components/research/DistributionChannelsPanel.tsx` | Distribution channel cards |
| `src/components/research/ResearchRisksPanel.tsx` | Risk cards |
| `src/components/research/ResearchHypothesesPanel.tsx` | Research hypothesis cards |
| `src/components/research/ResearchEvidencePanel.tsx` | Evidence cards |
| `src/components/research/ResearchNextActionCard.tsx` | Next research action resolver/card |
| `src/components/research/ResearchStatusBadge.tsx` | Small status, priority, confidence, severity badge |
| `src/components/research/ResearchOverviewCard.tsx` | Compact Overview tab research summary |
| `src/components/research/ResearchRailCard.tsx` | Compact right-rail research summary |
| `src/components/workspace/tabs/ResearchTab.tsx` | Workspace tab wrapper |
| `HANDOFF_research-mode-ui.md` | This handoff |

## Files Modified

| File | Change |
|------|--------|
| `src/components/workspace/WorkspaceTabs.tsx` | Added Research tab after Overview |
| `src/components/workspace/BusinessWorkspace.tsx` | Added Research tab routing and rendering |
| `src/components/workspace/tabs/OverviewTab.tsx` | Added compact Research summary card |
| `src/components/workspace/WorkspaceRightRail.tsx` | Added compact Research rail card |
| `src/components/workspace/next-action.ts` | Added research-aware primary next actions |
| `src/components/workspace/CommandMenuHint.tsx` | Added Research and Validation shortcuts |

## Components Added

- `ResearchWorkspacePanel`
- `ResearchEmptyState`
- `OpportunityScoreCard`
- `ResearchSummaryHeader`
- `CustomerSegmentsPanel`
- `BuyerBudgetPanel`
- `CompetitorMapPanel`
- `MonetizationPanel`
- `DistributionChannelsPanel`
- `ResearchRisksPanel`
- `ResearchHypothesesPanel`
- `ResearchEvidencePanel`
- `ResearchNextActionCard`
- `ResearchStatusBadge`
- `ResearchOverviewCard`
- `ResearchRailCard`
- `ResearchTab`

## API Routes Consumed

- `GET /api/businesses/[id]/research`
- `POST /api/businesses/[id]/research`
- `POST /api/businesses/[id]/research/segments`
- `PATCH /api/businesses/[id]/research/segments`
- `POST /api/businesses/[id]/research/buyer-budgets`
- `PATCH /api/businesses/[id]/research/buyer-budgets`
- `POST /api/businesses/[id]/research/competitors`
- `PATCH /api/businesses/[id]/research/competitors`
- `POST /api/businesses/[id]/research/monetization`
- `PATCH /api/businesses/[id]/research/monetization`
- `POST /api/businesses/[id]/research/distribution`
- `PATCH /api/businesses/[id]/research/distribution`
- `POST /api/businesses/[id]/research/risks`
- `PATCH /api/businesses/[id]/research/risks`
- `POST /api/businesses/[id]/research/hypotheses`
- `PATCH /api/businesses/[id]/research/hypotheses`
- `POST /api/businesses/[id]/research/evidence`

## UI States Handled

- Loading workspace
- Empty workspace with Generate research workspace CTA
- Generate in progress and generate failure
- Backend unavailable
- Research schema missing
- Unauthenticated user
- Network error
- Workspace with no segments, buyer budgets, competitors, monetization models, distribution channels, risks, hypotheses, or evidence
- Client helper friendly errors for create/update failures

## Manual QA Plan

1. Open `/dashboard` and confirm saved business cards still render.
2. Open a business detail page and confirm the tab bar includes Research after Overview.
3. Open the Research tab and confirm loading, empty, or populated states render.
4. For an empty workspace, click Generate research workspace and confirm seeded content renders.
5. Confirm opportunity score, thesis, target customer, money pool, wedge, and recommendation render.
6. Confirm segments, buyer budgets, competitors, monetization, distribution, risks, hypotheses, and evidence render.
7. Confirm Overview shows the compact Research card without making the page scroll-heavy.
8. Confirm the right rail shows the compact Research row/card.
9. Resize to 390px and confirm the tab bar scrolls, cards stack, long text wraps, and no horizontal overflow appears.

## Known Limitations

- The compact UI currently reads research records and generates the starter workspace; create/update helper functions are available but detailed editing forms are intentionally not surfaced.
- Overview and right rail fetch the full research workspace because no summary-only client route is exposed.
- Generate is controlled by the backend and may append duplicates if called outside the empty-state UI.
- Manual authenticated QA requires local Supabase env values; this branch did not create or print `.env.local`.

## Intentionally Deferred

- Agent Registry
- Agent Runs
- Market Research Agent
- Competitor enrichment agent
- Opportunity scoring agent
- Promotion flow that automatically copies research hypotheses into Customer Validation
- Detailed create/edit forms for every research entity
- Supabase SQL application
