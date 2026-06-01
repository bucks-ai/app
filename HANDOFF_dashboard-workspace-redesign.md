# HANDOFF: Dashboard / Workspace Redesign

**Branch:** `feature/dashboard-workspace-redesign`
**Worktree:** `/Users/satvikranga/bucks-ai-dashboard-workspace-redesign`
**Status:** Complete. `./scripts/check.sh` passing. Browser QA done with documented auth limits.

## Purpose

Make the signed-in dashboard and business workspace feel like a clean AI operating
system: premium, smooth, light/dark compatible, easy to scan, sidebar-driven, low on
scrolling, with an obvious next action. Bring both surfaces in line with the
homepage/design foundation (semantic tokens, theme toggle) that was merged into main as
commit `0a682fd`.

## Codex interrupted state (before this work)

Codex had started the redesign in this worktree with uncommitted WIP:

- Added `WorkspaceSidebar.tsx` (desktop left nav) and `WorkspaceSectionHeader.tsx`.
- Reworked `BusinessWorkspace`, `WorkspaceTabs`, `PrimaryActionStrip`,
  `WorkspaceRightRail`, `OverviewTab`, `BusinessCard`, and several tab files.
- Left `src/app/dashboard/page.tsx` mid-edit: it still rendered `ToolPermissionSummary`
  and `demoPermissions` in JSX after their imports were removed, so the page would not
  compile.
- The branch was one commit behind main and did not yet include the design foundation.
- No checks or QA had been run.

## Claude continuation summary

- Merged latest `main` (`0a682fd`) into the branch as a fast-forward to bring in the
  design foundation, keeping Codex's WIP intact.
- Fixed the broken dashboard page and finished the redesign.
- Migrated the hardcoded dashboard/workspace colors (and the feature components they
  embed) to semantic tokens so both light and dark mode work.
- Restructured the business detail route so the workspace is a full-bleed app shell
  instead of being nested inside the constrained marketing `DashboardShell`.
- Ran `./scripts/check.sh` (install, lint, build): passing.
- Browser QA in light, dark, and at 390px, including a temporary demo-data preview of the
  workspace shell that was removed before commit.

## Token migration

Replaced raw hex utility values with the semantic tokens from `globals.css` across:
`src/app/dashboard`, `src/components/dashboard`, `src/components/workspace` (+ `tabs`),
and the feature folders `execution`, `github`, `vercel`, `deployment`, `tools`,
`research`, `validation`, `agents`, plus the shared `ui` primitives.

Mapping used:

- surfaces -> `bg-background` / `bg-surface` / `bg-elevated`
- lines -> `border-border` (and `border-border-subtle`)
- text -> `text-foreground` / `text-secondary` / `text-muted`
- brand -> `accent` / `accent-hover` / `accent-contrast`
- status -> `success` / `warning` / `error`

Solid accent buttons use `text-accent-contrast` (white in both themes) so they stay
readable in light mode. Solid amber/green chips use `text-background`, which flips
correctly per theme.

## Files created

- `src/components/workspace/WorkspaceSidebar.tsx` (started by Codex, finished and
  tokenized here)
- `src/components/workspace/WorkspaceSectionHeader.tsx` (started by Codex, tokenized here)
- `HANDOFF_dashboard-workspace-redesign.md` (this file)
- A temporary `.claude/launch.json` was created for the local preview server. `.claude/`
  is gitignored, so it is not committed.

## Files modified

About 94 files. The structural and visual ones:

- Dashboard: `src/app/dashboard/page.tsx`, `src/components/dashboard/BusinessCard.tsx`,
  `src/components/dashboard/DashboardShell.tsx`
- Workspace shell: `src/app/dashboard/businesses/[id]/page.tsx`,
  `src/components/workspace/BusinessWorkspace.tsx`, `WorkspaceHeader.tsx`,
  `WorkspaceTabs.tsx`, `PrimaryActionStrip.tsx`, `WorkspaceRightRail.tsx`
- Overview: `src/components/workspace/tabs/OverviewTab.tsx`
- Shared primitive: `src/components/ui/OperatorPanel.tsx` (`rounded-card` + soft shadow)

The remaining modified files are mostly token swaps inside the tab wrappers and feature
components, with no logic changes.

## Dashboard changes

- Replaced the oversized hero panel with a compact header: a "Mission Control" eyebrow, a
  "Your businesses" title, a short subtitle, and two clear CTAs (New business, Tool
  registry).
- Added a slim three-metric row (businesses, approvals, recent logs).
- Two-column layout: scannable business cards on the left, a compact "Needs you" plus
  "Recent activity" side column on the right.
- Polished empty state that explains what bucks.ai does, with a "Start with an idea" CTA.
- Removed the broken Tool permissions section.
- `BusinessCard` now has a consistent layout (status, type, name, one-line idea, progress
  bar, approvals/blockers, last activity, next action), a soft card with a hover lift, and
  an "Open" CTA with correct light-mode contrast.

## Workspace and sidebar changes

- The business detail route renders `Navbar` plus a full-bleed workspace instead of
  nesting the app shell inside the marketing `DashboardShell`, which had boxed it in with a
  max width, top padding, and a grid background, and broke the sticky bars.
- `BusinessWorkspace` is now a three-region shell: a left sidebar (lg and up), a main
  column with a sticky command bar (header plus the primary action strip on desktop, the
  tab strip on mobile), and a right status rail (2xl only).
- Sticky offsets are set to the measured 69px navbar height so nothing slides under the
  navbar.
- `WorkspaceSidebar` has grouped navigation (Plan / Build / Operate) with numbered
  markers, a clear active state, a compact identity card, and the command-menu hint. All
  ten sections are present.
- `WorkspaceHeader` is a slim identity bar (back link, name, phase and health pills, asset
  shortcuts, blueprint button) with a thin progress line.
- `WorkspaceTabs` scrolls horizontally on mobile with a clear active underline.
- Mobile: the sidebar collapses to the horizontal tab strip, and a fixed bottom bar keeps
  the next action reachable.

## Overview cleanup

- The Overview is now a command center: a snapshot (name, one-line idea, progress,
  milestones, approvals, blockers, current phase, milestone chips), a primary-next-action
  card, four compact feature cards (Research, Validation, Deployment, Team), and a compact
  business summary plus latest-activity row.
- Removed the duplicate "Key assets" and "Tool queue" sections, since those live in their
  own tabs, the header, and the rail. The Overview is shorter and easier to scan.
- Metric tiles are two-up on mobile to keep the section short.

## Right rail changes

- Reduced from seven cards to four: next action, progress snapshot (with approvals and
  blockers), key blockers, and a deploy plus assets block.
- Removed the duplicated activity feed and the separate approvals list. The rail shows
  only on 2xl screens, so it never dominates the page or forces horizontal overflow.

## Feature tab polish

- The tabs are thin wrappers (section header plus the existing feature panel). No feature
  logic changed.
- All feature panels (research, validation, agents, deployment, github, vercel, execution,
  tools) were tokenized so they are theme-aware. Empty and error states render cleanly.

## Light / dark compatibility

- Dashboard and workspace surfaces use semantic tokens and respond to the theme toggle.
- Both modes look intentional. There are no hardcoded black or white seams in the
  dashboard or workspace.
- The shared marketing surfaces that reuse the same primitives (for example `/tools`) also
  became theme-aware in light mode as a side effect, which matches the design foundation's
  stated intent.

## Typography

- Uses the existing Geist foundation. Hierarchy was improved with size, weight, tracking,
  and spacing. No new fonts were added.

## QA performed

- `./scripts/check.sh`: install, lint, and build all pass.
- Browser QA against the worktree dev server:
  - `/dashboard` in dark, light, and at 390px. No horizontal overflow
    (`scrollWidth === clientWidth` at 390px). Cards stack, the desktop "Open" button hides
    on mobile, and the setup/sign-in/demo states render.
  - The workspace shell through a temporary demo-data preview page (removed before commit):
    desktop at 1280 (sidebar plus content) and 1600 (sidebar, content, and rail), in dark
    and light, and at 390px (tab strip plus the fixed bottom bar). No horizontal overflow.
    No console errors.
  - The Team tab and `/tools` render cleanly (tokenized empty state and light mode).

## Known limitations

- The authenticated workspace with real Supabase data could not be exercised. The worktree
  has no `.env.local` and there is no headless session, so `/dashboard` shows the setup or
  sign-in state and the business route shows the auth state panel. The workspace shell was
  QA'd with demo data through a temporary preview page instead. Populated feature-panel
  states (research with data, the 21-agent team grid, a live deployment) were validated by
  a successful build and code review, not visually.
- Pre-existing Next.js workspace-root warning from multiple `package-lock.json` files (home
  directory, main repo, worktree). It was not introduced or addressed here and is already
  listed in `TASKS.md`.

## Intentionally not touched

- No changes to auth, data-fetching semantics, routes, or server actions.
- No backend APIs, Supabase SQL, or migrations.
- No GitHub or Vercel automation changes.
- No new product nodes, runner, or UI libraries.
- The public home page was not edited. The design foundation it relies on came from the
  merge, not from changes here.

## Safety confirmations

- No SQL was written or applied. No secrets were printed or committed. No backend changes.
- `package-lock.json`: unchanged, so no restore was needed.
- `.env.local` is not present in the worktree and was not committed.
