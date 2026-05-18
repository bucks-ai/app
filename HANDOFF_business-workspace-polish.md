# Business Workspace Polish Handoff

## Summary

Second pass of the dashboard UX refactor. The architecture branch had already moved business detail into a tabbed workspace; this pass tightened the surface so the founder sees the current stage, health, next required action, assets, tool queue, and recent activity without scrolling through every object as a large card.

## Files created

- `src/components/workspace/next-action.ts` — Shared primary next-action resolver with defensive fallbacks and no API calls.
- `src/components/workspace/CompactToolQueue.tsx` — Compact expandable tool approval rows for overview, right rail, and full Tools-tab summary.
- `src/components/workspace/CompactActivityCenter.tsx` — Dense filtered activity rows for overview/rail and the Activity tab.
- `src/components/workspace/AssetQuickLinks.tsx` — Compact GitHub, Vercel, live URL, blueprint, and tool setup links with pending states.
- `src/components/workspace/CommandMenuHint.tsx` — Lightweight local command shortcut modal placeholder.
- `HANDOFF_business-workspace-polish.md` — This handoff.

## Files modified

- `src/components/workspace/BusinessWorkspace.tsx` — Sticky action/tab band, command hint, mobile sticky next-action bar, and compact rail integration.
- `src/components/workspace/PrimaryActionStrip.tsx` — Reused shared next-action resolver and made the CTA more prominent and descriptive.
- `src/components/workspace/WorkspaceHeader.tsx` — Added latest run signal and tightened responsive header behavior.
- `src/components/workspace/WorkspaceRightRail.tsx` — Rebuilt rail around required next action, compact tool queue, compact assets, and compact activity.
- `src/components/workspace/WorkspaceTabs.tsx` — Adjusted layout to work inside sticky workspace controls.
- `src/components/workspace/tabs/OverviewTab.tsx` — Removed large activity/assets blocks in favor of compact modules and shorter blueprint disclosure.
- `src/components/workspace/tabs/ActivityTab.tsx` — Replaced custom list with shared filtered compact activity center.
- `src/components/workspace/tabs/ToolsTab.tsx` — Added compact approval queue above detailed tool controls.
- `src/components/dashboard/BusinessCard.tsx` — Rebuilt saved-business cards as command queue re-entry cards.
- `src/app/dashboard/page.tsx` — Passed per-business human actions/activity into cards and updated dashboard copy/density.
- `PROJECT_STATE.md`, `TASKS.md`, `AI_CHANGELOG.md` — Updated project state and session history.

## UX improvements

- Above the fold now prioritizes identity, phase, health, progress, latest run status, blocker/approval counts, primary CTA, and key assets.
- Primary next action uses the shared priority order: blockers, human actions, GitHub, scaffold, Vercel, failed runs, validation, activity.
- Overview no longer competes with full logs, full blueprint text, full tool cards, and execution controls in one scroll.
- Tool approvals appear as compact rows with expandable detail in overview/right rail.
- Activity is dense, newest first, filterable, and full history lives in Activity.
- Assets are quick links with muted pending states.
- GitHub and Vercel controls remain in Build/Deploy or relevant action paths.

## Dashboard re-entry

- Saved business cards now show progress estimate, blocker count, approval count, repo status, deploy status, last activity, and an Open Workspace CTA.
- Dashboard copy frames the list as a command queue instead of a gallery.
- Real dashboard cards use existing business, human action, and activity data without adding extra execution-status API calls.

## Mobile behavior

- Workspace controls are sticky.
- Tabs scroll horizontally.
- Desktop right rail remains hidden on smaller screens.
- Mobile bottom bar always shows the primary next action plus Activity.
- Rows/buttons are constrained to avoid horizontal overflow around 390px.

## Remaining known limitations

- Dashboard progress is a graceful fallback estimate because execution status is not fetched for the list view.
- The command menu is intentionally a local shortcut placeholder, not a full Cmd+K command system.
- Detailed tool update controls still live in the Tools tab via the existing permission control room.
- Existing Next.js multiple-lockfile workspace-root warning remains.

## Manual QA plan

- `/dashboard` signed out and signed in states.
- Saved business cards with and without human actions.
- Business detail Overview, Actions, Build, Deploy, Tools, Activity, Settings tabs.
- Mobile width around 390px for tabs, sticky bottom action, row wrapping, and no horizontal overflow.
- GitHub repo creation remains reachable in Build.
- Vercel project creation remains reachable in Deploy.
- Tool approvals still work in Tools.
- Logs/history remain visible and filterable in Activity.
