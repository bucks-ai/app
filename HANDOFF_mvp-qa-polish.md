# HANDOFF: MVP QA / Demo Polish

**Branch:** `feature/mvp-qa-polish`
**Date:** 2026-06-01
**Status:** QA pass complete

## Purpose

This pass verifies the merged MVP demo surfaces after Customer Validation, Research Mode,
Agent Registry, Agent Runs, and Operating Team UI. It keeps changes intentionally small:
layout polish, docs, and QA documentation only.

No Supabase SQL was applied. No secrets were printed. No external integrations were added.

## QA Performed

### Automated

`./scripts/check.sh` passed on the feature worktree.

The script ran:

- `npm install`
- `npm run lint`
- `npm run build`

`npm install` reported 2 moderate audit findings and suggested `npm audit fix --force`.
That command was not run.

### Browser Smoke Tests

Local dev server:

```text
http://localhost:3000
```

Desktop routes checked:

| Route | Result |
| --- | --- |
| `/dashboard` | Rendered signed-out dashboard with 3 sample business cards |
| `/dashboard/businesses/acme-analytics?tab=team` | Rendered signed-out business detail gate |
| `/intake` | Rendered intake page |
| `/tools` | Rendered tool registry |
| `/login` | Rendered login page |
| `/signup` | Rendered signup page |

Browser console check returned no warnings or errors during the smoke pass.

### Mobile

At 390px viewport width, no horizontal overflow was detected on:

- `/dashboard`
- `/dashboard/businesses/acme-analytics?tab=team`
- `/intake`
- `/tools`
- `/login`
- `/signup`

## Polish Changes

- Compacted the Overview tab by placing Validation, Research, and Operating Team summary cards in a responsive 3-column grid on wide screens.
- Cleaned up small indentation/import rough edges in workspace components.

## Authenticated QA Limitations

The browser session was signed out, so full authenticated workspace QA could not verify:

- Real saved business detail data
- Research generate/display states against a signed-in business
- Validation seed/display states against a signed-in business
- Operating Team tab rendering all 21 agents against a signed-in business
- Agent run history inference button with persisted `agent_runs`
- GitHub repo creation, scaffold preparation, Vercel project creation, and deployment status actions
- Tools approval mutations

The signed-out business detail route rendered safely and the app build includes all dynamic API routes.

## Follow-Up QA Checklist

Use a signed-in browser session with a real saved business:

- Open a saved business workspace.
- Confirm tabs appear in order: Overview, Research, Actions, Build, Deploy, Validation, Team, Tools, Activity, Settings.
- Confirm Overview remains compact with the Validation, Research, and Team summaries grouped.
- Generate or view Research workspace.
- Seed or view Validation workspace.
- Open Team and confirm 21 agents render by node.
- Run agent history inference after confirming `agent_runs` SQL is applied.
- Confirm Deploy, Tools, Activity, and Settings tabs still render and route correctly.

## Known Limitations

- Local QA could not prove signed-in flows without an authenticated browser session.
- The Next.js workspace-root warning remains known existing repo housekeeping and was not changed in this scope.
- `npm install` may add package-lock peer metadata locally; it should be restored unless dependencies are intentionally changed.
