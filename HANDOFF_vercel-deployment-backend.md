# Handoff: vercel-deployment-backend

Branch: `feature/vercel-deployment-backend`
Date: 2026-05-13

---

## Files Created

| File | Purpose |
|---|---|
| `src/lib/vercel/env.ts` | Env helpers: `hasVercelEnv()`, `getVercelEnv()`, `getVercelSetupMessage()` — safe to import without env vars |
| `src/types/vercel.ts` | Vercel types: `CreateVercelProjectInput`, `VercelProjectRecord`, `VercelDeploymentRecord`, `CreateVercelProjectResult`, `VercelApiError`, `VercelEnvironmentVariableInput` |
| `src/lib/vercel/client.ts` | Server-only API client: `getVercelUser()`, `createVercelProject()`, `createVercelEnvironmentVariables()`, `listVercelDeployments()`, `getVercelProject()`, `triggerVercelDeploymentIfSupported()`, `createVercelProjectWithSetup()` |
| `src/lib/github/next-scaffold.ts` | `prepareDeployableNextScaffold()` — writes 7 files to an existing GitHub repo to make it deployable with Next.js |
| `src/lib/vercel/project-metadata.ts` | `getLatestVercelProjectForBusiness(businessId)` — reads Vercel metadata from `agent_activity_logs` |
| `src/app/api/github/prepare-next-scaffold/route.ts` | `POST /api/github/prepare-next-scaffold` — writes Next.js scaffold to the existing GitHub repo |
| `src/app/api/vercel/create-project/route.ts` | `POST /api/vercel/create-project` — creates a Vercel project linked to GitHub repo, optionally scaffolds first |
| `src/app/api/vercel/project-status/route.ts` | `GET /api/vercel/project-status?businessId=...` — returns stored metadata + live deployments |
| `HANDOFF_vercel-deployment-backend.md` | This file |

## Files Modified

| File | Change |
|---|---|
| _(none)_ | No existing files were modified |

---

## API Routes Added

### `POST /api/github/prepare-next-scaffold`

Writes a minimal deployable Next.js 15 scaffold to the existing GitHub repo.

**Request body:**
```json
{ "businessId": "<uuid>" }
```

**Success response:**
```json
{
  "ok": true,
  "data": {
    "filesWritten": ["package.json", "next.config.ts", "tsconfig.json", "src/app/globals.css", "src/app/layout.tsx", "src/app/page.tsx", "README.md"],
    "repoUrl": "https://github.com/owner/repo",
    "activityLogId": "<uuid>"
  }
}
```

**Error codes:**

| Code | HTTP | Meaning |
|---|---|---|
| `missing_supabase_env` | 503 | Supabase env vars absent |
| `invalid_input` | 400 | Missing `businessId` |
| `unauthenticated` | 401 | No valid session |
| `forbidden` | 403 | Wrong owner |
| `business_not_found` | 404 | Business not found |
| `github_env_missing` | 503 | `GITHUB_PERSONAL_ACCESS_TOKEN` not set |
| `github_not_approved` | 403 | GitHub permission not approved |
| `github_repo_missing` | 400 | No GitHub repo found for this business |
| `scaffold_failed` | 500 | GitHub file write failed |

---

### `POST /api/vercel/create-project`

Creates a Vercel project linked to the business's GitHub repo.

**Request body:**
```json
{
  "businessId": "<uuid>",
  "projectName": "optional-override",
  "prepareScaffold": true,
  "createDeployment": false
}
```

- `projectName` — optional override; defaults to business name, sanitized
- `prepareScaffold` — if true, writes Next.js scaffold to the GitHub repo before creating the Vercel project
- `createDeployment` — if true, triggers a deployment from the latest git commit (best-effort)

**Success response:**
```json
{
  "ok": true,
  "data": {
    "projectId": "prj_xxx",
    "projectName": "my-startup",
    "dashboardUrl": "https://vercel.com/dashboard/my-startup",
    "deploymentUrl": "https://my-startup-abc.vercel.app",
    "warnings": []
  }
}
```

`deploymentUrl` is omitted if deployment was not requested or failed.
`warnings` is omitted if empty.

**Error codes:**

| Code | HTTP | Meaning |
|---|---|---|
| `missing_supabase_env` | 503 | Supabase env vars absent |
| `vercel_env_missing` | 503 | `VERCEL_TOKEN` not set |
| `invalid_input` | 400 | Missing/invalid `businessId` or unparsable project name |
| `unauthenticated` | 401 | No valid session |
| `forbidden` | 403 | Wrong owner |
| `business_not_found` | 404 | Business not found |
| `vercel_not_approved` | 403 | Vercel permission not approved |
| `github_repo_missing` | 400 | No GitHub repo found for this business |
| `scaffold_failed` | 500 | Scaffold write failed (only with `prepareScaffold: true`) |
| `vercel_create_failed` | 500 | Vercel API returned an error |

If project creation succeeds but deployment trigger fails, the route returns `ok: true` with a `warnings` array — the project is created and the activity log is written.

---

### `GET /api/vercel/project-status?businessId=...`

Returns stored Vercel project metadata and optionally live deployments.

**Success response (project exists):**
```json
{
  "ok": true,
  "data": {
    "vercelProject": {
      "projectId": "prj_xxx",
      "projectName": "my-startup",
      "dashboardUrl": "https://vercel.com/dashboard/my-startup",
      "deploymentUrl": null,
      "gitRepoFullName": "owner/repo",
      "productionBranch": "main",
      "createdAt": "2026-05-13T..."
    },
    "deployments": [...],
    "warnings": []
  }
}
```

**Success response (no project yet):**
```json
{
  "ok": true,
  "data": {
    "vercelProject": null,
    "deployments": []
  }
}
```

---

## Env Vars Required

| Variable | Required | Description |
|---|---|---|
| `VERCEL_TOKEN` | Yes | Vercel personal access token |
| `VERCEL_TEAM_ID` | No | Vercel team ID — required if your token belongs to a team account. If omitted, projects are created under the token owner's personal account. |

Both are already present as placeholders in `.env.example`.

### How to Create VERCEL_TOKEN

1. Vercel → Account Settings → Tokens
2. Click **Create Token**
3. Scope: **Full Account** (or select specific team)
4. Copy the token and add it to `.env.local`:
   ```
   VERCEL_TOKEN=xxxxxxxxxxxxxxxxxx
   VERCEL_TEAM_ID=team_xxxxxxxxx   # optional
   ```

> The token is **never** returned in any API response, logged to console, or exposed to the browser.

---

## Safety Model

- **Token is server-only.** `getVercelEnv()` is in `src/lib/vercel/env.ts` and only called from server-side route handlers and lib functions. It is never imported from any client component.
- **No secrets copied to generated projects.** The only env var set on the generated Vercel project is `NEXT_PUBLIC_BUCKS_AI_BUSINESS_ID` (a non-secret public identifier). `OPENAI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `VERCEL_TOKEN`, and all other bucks.ai secrets are intentionally excluded.
- **Vercel permission gate.** The route checks that a `vercel` tool permission exists for the business and has status `approved` or `connected_demo` before calling the API.
- **Ownership enforced.** Every route verifies `businesses.user_id = auth.uid()`.
- **No domains created.** The project creation payload does not include any custom domain configuration.
- **No payments, no emails.** The scaffold contains no Stripe, no Resend, no outbound email.
- **Deployment trigger is best-effort.** If `createDeployment: true` and the trigger fails (e.g. GitHub integration not set up), the route returns `ok: true` with a `warnings` array rather than failing the whole request.

---

## What Metadata Is Stored

In `agent_activity_logs` with `activity_type = "vercel_project_created"`:

```json
{
  "vercelProjectId": "prj_xxx",
  "vercelProjectName": "my-startup",
  "vercelDashboardUrl": "https://vercel.com/dashboard/my-startup",
  "vercelDeploymentUrl": null,
  "gitRepoFullName": "owner/repo",
  "productionBranch": "main",
  "warnings": []
}
```

Read it back with `getLatestVercelProjectForBusiness(businessId)` from `src/lib/vercel/project-metadata.ts`.

In `agent_activity_logs` with `activity_type = "github_next_scaffold_prepared"`:

```json
{
  "owner": "owner",
  "repo": "repo-name",
  "filesWritten": ["package.json", "next.config.ts", ...]
}
```

---

## What Secrets Are Intentionally Not Copied

The following bucks.ai env vars are **never** set on generated Vercel projects:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `NEXT_PUBLIC_SUPABASE_URL` (bucks.ai's own Supabase instance)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `GITHUB_PERSONAL_ACCESS_TOKEN`
- `VERCEL_TOKEN`
- `STRIPE_SECRET_KEY`
- `RESEND_API_KEY`

---

## How to Manually Test

Requires: `.env.local` with real Supabase + GitHub + Vercel credentials, `npm run dev` running, a valid Supabase session.

```bash
# 1. Prepare scaffold (logged out → 401)
curl -X POST http://localhost:3000/api/github/prepare-next-scaffold \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>"}'
# → { ok: false, code: "unauthenticated" }

# 2. Vercel env missing → 503
# (temporarily remove VERCEL_TOKEN from .env.local)
curl -b <session> -X POST http://localhost:3000/api/vercel/create-project \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>"}'
# → { ok: false, code: "vercel_env_missing" }

# 3. Vercel not approved → 403
# (Vercel permission seeded but status is approval_requested)
curl -b <session> -X POST http://localhost:3000/api/vercel/create-project \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>"}'
# → { ok: false, code: "vercel_not_approved" }

# 4. Approve Vercel permission
curl -b <session> -X PATCH http://localhost:3000/api/tool-permissions/<vercel-permission-uuid> \
  -H "Content-Type: application/json" \
  -d '{"action":"approve"}'

# 5. No GitHub repo → 400
# (business has no github_repo_created activity log)
curl -b <session> -X POST http://localhost:3000/api/vercel/create-project \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>"}'
# → { ok: false, code: "github_repo_missing" }

# 6. Create GitHub repo first (if not done)
curl -b <session> -X POST http://localhost:3000/api/github/create-repo \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>"}'

# 7. Prepare scaffold + create Vercel project
curl -b <session> -X POST http://localhost:3000/api/vercel/create-project \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>","prepareScaffold":true,"createDeployment":true}'
# → { ok: true, data: { projectId: "...", projectName: "...", dashboardUrl: "...", warnings?: [...] } }

# 8. Check project status
curl -b <session> http://localhost:3000/api/vercel/project-status?businessId=<uuid>
# → { ok: true, data: { vercelProject: {...}, deployments: [...] } }

# 9. Verify in Vercel dashboard:
#    - Project created under your account/team
#    - GitHub repo linked
#    - NEXT_PUBLIC_BUCKS_AI_BUSINESS_ID env var set
# 10. Check agent_activity_logs in Supabase:
#     - activity_type = "vercel_project_created"
#     - metadata contains projectId, projectName, etc.
#     - activity_type = "github_next_scaffold_prepared" (if scaffold was requested)
```

---

## Known Limitations

- **GitHub integration must be authorized on Vercel.** Linking a GitHub repo to a Vercel project requires that the Vercel account has already connected to GitHub via the Vercel dashboard. If not authorized, the `gitRepository` field in project creation may be accepted by the API but the link will not be functional until the user completes GitHub authorization in the Vercel UI.
- **Deployment trigger requires linked GitHub integration.** `triggerVercelDeploymentIfSupported` passes a `gitSource` payload, but Vercel may reject or silently queue this if the GitHub integration is not fully set up. It returns a warning rather than an error in that case.
- **One token, one account.** All projects are created under the token owner's personal account or the specified team. Multi-tenant per-user project creation is not supported until OAuth is implemented.
- **Project name conflicts.** Vercel returns an error if a project with the same name already exists in the account. The route does not check for duplicates before calling the API.
- **`createDeployment: false` by default.** The first deployment typically happens automatically when the user pushes to the linked GitHub repo. Explicit deployment triggers (`createDeployment: true`) require an initial commit to exist.

---

## What Is Intentionally Deferred

- **Vercel OAuth** — proper per-user auth. Current PAT is dev/demo only.
- **Custom domains** — not created; would require DNS configuration.
- **Environment variable propagation** — the generated project gets one public identifier. Real app env vars (API keys, DB URLs) must be set manually in the Vercel dashboard by the founder.
- **Deployment webhook / status polling** — no listener for Vercel deployment events back into bucks.ai.
- **UI wiring** — no frontend components for triggering these API routes yet.

---

## Recommended Next Task

**Branch: `feature/vercel-deployment-ui`**

Wire a "Deploy to Vercel" panel into the business detail page:

1. Read the current Vercel tool permission status — show "Approve Vercel" CTA if not approved.
2. Once approved, show a "Deploy to Vercel" button that POSTs to `/api/vercel/create-project`.
3. Include a checkbox: "Prepare deployable scaffold first" (sets `prepareScaffold: true`).
4. On success, show the `dashboardUrl` as a link and display a status card from `GET /api/vercel/project-status`.
5. If a project already exists, show the existing project link instead of the create button.
