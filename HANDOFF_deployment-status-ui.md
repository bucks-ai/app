# Deployment Status UI Handoff

## Summary

Added a deployment status surface for the business workspace Deploy tab. The UI consumes the expected deployment status backend routes when available and falls back to existing Vercel project data when the backend route is missing.

## Files created

- `src/types/deployment-ui.ts` — UI-facing deployment status contracts.
- `src/lib/deployment-client.ts` — Client-safe fetch helpers for deployment status and refresh.
- `src/components/deployment/DeploymentStatusCard.tsx` — Main deployment status panel.
- `src/components/deployment/DeploymentStatusBadge.tsx` — Compact status badge and label helpers.
- `src/components/deployment/LiveAppLink.tsx` — Live app CTA.
- `src/components/deployment/DeploymentRefreshButton.tsx` — Refresh action button.
- `HANDOFF_deployment-status-ui.md` — This handoff.

## Files modified

- `src/components/workspace/tabs/DeployTab.tsx` — Places deployment status above project creation and execution details.
- `src/components/workspace/AssetQuickLinks.tsx` — Shows Live App URL, Vercel Project, and GitHub Repo with deployment pending fallback.
- `src/components/workspace/WorkspaceHeader.tsx` — Adds compact deployment status to the header.
- `src/components/workspace/WorkspaceRightRail.tsx` — Adds a compact deployment status row that opens Deploy.
- `src/components/dashboard/BusinessCard.tsx` — Shows deploy status from existing card data only.
- `src/lib/deployment-client.ts` — Normalizes current and expected backend response shapes.

## UI states

- Not deployed / no project: muted status with “No Vercel project yet” and a Deploy-tab project creation CTA.
- Queued: amber status with refresh CTA.
- Building: indigo status with refresh CTA.
- Live / ready: green status with primary “Open live app” CTA.
- Failed: red status with “Open Vercel” CTA when a dashboard URL exists.
- Manual action required: amber status with “Connect Git or push to main in Vercel/GitHub.”
- Unknown: muted status with refresh available.
- Backend missing: shows “Deployment status backend is not available yet. Merge backend branch first.”

## Expected backend routes

- `GET /api/vercel/project-status?businessId=...`
- `POST /api/vercel/refresh-deployment-status`

The client accepts `data.vercelProject` plus `data.deployments`, or a pre-normalized deployment view if the backend branch returns one.

## Manual QA

- Open a business workspace and switch to Deploy.
- Confirm the deployment status card renders above Vercel project creation controls.
- With no refresh backend route, click Refresh status and confirm the backend-pending fallback message appears.
- Confirm a returned live URL appears as the primary “Open live app” CTA and in Asset Quick Links.
- Confirm Vercel Project and GitHub Repo links still render when known.
- Check a mobile viewport around 390px for wrapping and no horizontal overflow.
