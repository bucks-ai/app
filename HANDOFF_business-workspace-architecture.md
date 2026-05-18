# Handoff: Business Workspace Architecture

## Summary

Refactored the business detail page from a long vertically-stacked report into a tabbed stateful project workspace. All existing features remain reachable; the presentation layer is now a workspace shell with persistent header, sticky action strip, tabbed content, and a desktop right rail.

---

## Files Created

### Workspace Shell

| File | Purpose |
|------|---------|
| `src/components/workspace/BusinessWorkspace.tsx` | Main orchestrator — assembles all workspace components |
| `src/components/workspace/WorkspaceHeader.tsx` | Compact persistent header with status, progress, and quick assets |
| `src/components/workspace/PrimaryActionStrip.tsx` | Sticky action strip showing highest-priority next action |
| `src/components/workspace/WorkspaceTabs.tsx` | Tab bar with URL sync (`?tab=build` etc.) |
| `src/components/workspace/WorkspaceRightRail.tsx` | Desktop sticky right rail (next actions, blockers, assets, activity) |
| `src/components/workspace/WorkspaceDrawer.tsx` | Slide-in drawer primitive (used for blueprint, extensible) |

### Tab Content

| File | Tab | Content |
|------|-----|---------|
| `src/components/workspace/tabs/OverviewTab.tsx` | Overview | Summary stats, milestone stepper, blueprint card, next actions, recent activity |
| `src/components/workspace/tabs/ActionsTab.tsx` | Actions | Unified list: approvals + blockers + next actions, sorted by urgency |
| `src/components/workspace/tabs/BuildTab.tsx` | Build | Step-list: GitHub approved → repo created → scaffold prepared |
| `src/components/workspace/tabs/DeployTab.tsx` | Deploy | Wraps existing `DeploymentExecutionPanel` |
| `src/components/workspace/tabs/ToolsTab.tsx` | Tools | Wraps existing `PermissionControlRoom` |
| `src/components/workspace/tabs/ActivityTab.tsx` | Activity | Dense filtered event log (All / Runs / Tools / GitHub / Vercel / Human) |
| `src/components/workspace/tabs/SettingsTab.tsx` | Settings | Business metadata + enforced safety/autonomy boundaries |

---

## Files Modified

| File | Change |
|------|--------|
| `src/components/dashboard/BusinessDetail.tsx` | Reduced to thin wrapper — builds `initialExecutionStatus` and renders `BusinessWorkspace` |

No other files were modified. All routes, APIs, and backend behavior are unchanged.

---

## New Architecture

```
BusinessDetailPage (server component)
└── DashboardShell
    └── BusinessDetail (builds execution status, delegates to workspace)
        └── BusinessWorkspace (client orchestrator)
            ├── WorkspaceHeader     (compact — name, phase, health, progress, assets)
            ├── PrimaryActionStrip  (highest-priority next action + secondary pills)
            ├── WorkspaceTabs       (Overview / Actions / Build / Deploy / Tools / Activity / Settings)
            ├── main content
            │   ├── OverviewTab
            │   ├── ActionsTab
            │   ├── BuildTab       (uses GitHubRepoCard / GitHubRepoGate)
            │   ├── DeployTab      (uses DeploymentExecutionPanel)
            │   ├── ToolsTab       (uses PermissionControlRoom)
            │   ├── ActivityTab
            │   └── SettingsTab
            ├── WorkspaceRightRail  (desktop sticky, xl breakpoint)
            ├── mobile bottom bar   (sticky, xl:hidden)
            └── WorkspaceDrawer     (blueprint, closeable)
```

---

## Tab Structure

| Tab | Default | Key content |
|-----|---------|-------------|
| Overview | Yes | Stats, milestones, blueprint summary (truncated), next actions, latest activity, assets |
| Actions | No | All pending approvals + blockers + next actions in urgency order |
| Build | No | Step-list: GitHub permission → repo → scaffold |
| Deploy | No | Full DeploymentExecutionPanel |
| Tools | No | Full PermissionControlRoom |
| Activity | No | Dense filtered event log |
| Settings | No | Business info + safety boundaries |

Tab state is synced to `?tab=<key>` URL query param. Deep links work. No full page reload on tab switch.

---

## Right Rail Behavior

- Visible only at `xl` (1280px+) breakpoint
- Sticky inside the body column
- Sections: Next action (top 3) → Blockers → Pending approvals → Key assets → Recent activity (max 3)
- Each item links/navigates to the relevant tab

---

## Primary Action Strip Behavior

Resolves the highest-priority action in this order:
1. Human-required approvals (critical — "Needs you")
2. Active blockers (high — "Act now")
3. Founder-owned next actions from execution status
4. Phase-based fallback (e.g., phase = "github" → Build tab)
5. Auto next action from execution status
6. Default: "Review execution status" → Overview

CTA routes to the appropriate tab. Secondary pills show pending approval count, blocker count, and latest activity event.

---

## What Moved Where

| Old location | New location |
|---|---|
| Hero card (name, overview, type, goal) | WorkspaceHeader (compact) + SettingsTab (full) |
| ExecutionCommandCenter full view | Distributed across Overview + right rail |
| Blueprint summary section | Overview tab (truncated) + Blueprint drawer |
| Human-required actions section | Actions tab |
| Next autonomous actions section | Actions tab + Overview tab |
| Activity log section | Activity tab |
| Tool permissions section | Actions tab (summary), Tools tab (full) |
| Tool setup queue (PermissionControlRoom) | Tools tab |
| GitHub repo creation section | Build tab |
| Deployment execution panel | Deploy tab |

---

## Known Limitations

- The `ExecutionCommandCenter` (with its full milestone grid, blockers, next actions, assets, timeline) is no longer rendered as a standalone section. The equivalent data is surfaced per-tab. If you want to re-expose the full `ExecutionCommandCenter` view, it can be added as a sub-section of the Overview tab.
- `WorkspaceHeader` quick asset links are hidden on mobile (shown on `lg+`). On mobile, use the tab system or the right rail drawer.
- The `WorkspaceRightRail` is desktop-only (`xl+`). On mobile, core data is accessible via the tabs.
- `ActivityTab` uses `timeline` from execution status when available, otherwise falls back to `business.activity`. Runs filter is based on string matching on `category`; a typed category enum would improve filter precision.
- Blueprint drawer shows the summary text and next autonomous actions. Full blueprint (phases, tools, etc.) requires the raw blueprint object from the page — not yet passed through.

---

## Manual QA Plan

1. Navigate to `/dashboard` — should render without error.
2. Click into a saved business — workspace shell should appear.
3. Verify workspace header shows: business name, health pill, phase pill, progress bar.
4. Verify primary action strip shows a non-empty CTA above the fold.
5. Click each tab — all should render without crashing.
6. Check Build tab — GitHub gate or GitHub card should be visible.
7. Check Deploy tab — DeploymentExecutionPanel should render.
8. Check Tools tab — PermissionControlRoom should render.
9. Check Activity tab — filter buttons should work.
10. Check Settings tab — business info and safety boundaries visible.
11. Open Blueprint drawer via the "Blueprint" button in the header.
12. On desktop (1280px+), verify right rail is visible with next action / blockers.
13. On mobile width (<1280px), verify no horizontal overflow, tab bar scrolls horizontally.
14. Verify `?tab=build` URL param works on direct navigation.
15. Verify signed-out and not-found states still display their state panels (from page.tsx).

---

## Recommended Next Polish Pass

- Pass the raw blueprint object through to `BusinessWorkspace` so the Blueprint drawer can show phases, tools, and the full structured output.
- Add a tab badge on Actions showing pending approval count (currently shows approval + blocker count combined).
- Add skeleton loaders per tab while execution status is loading.
- Add `ExecutionCommandCenter` as an optional collapsible sub-section in Overview for power users.
- Add mobile sheet/drawer for the right rail content (currently omitted on mobile).
- Add keyboard navigation for the tab bar.
- Activity tab: replace string-match category filtering with typed category from the API.
