# Handoff: github-repo-backend

Branch: `feature/github-repo-backend`
Date: 2026-05-13

---

## Files Created

| File | Purpose |
|---|---|
| `src/types/github.ts` | GitHub types: `GitHubRepoVisibility`, `CreateGitHubRepoInput`, `GitHubRepoRecord`, `CreateGitHubRepoResult`, `GitHubFileTemplate` |
| `src/lib/github/env.ts` | Env helpers: `hasGitHubEnv()`, `getGitHubEnv()`, `getGitHubSetupMessage()` — safe to import without env vars |
| `src/lib/github/client.ts` | Server-only API client: `getAuthenticatedGitHubUser()`, `createGitHubRepository()`, `createOrUpdateGitHubFile()`, `createStarterRepositoryFiles()` |
| `src/lib/github/repo-metadata.ts` | Read helper: `getLatestGitHubRepoForBusiness(businessId)` — queries `agent_activity_logs` for `github_repo_created` entries |
| `src/app/api/github/create-repo/route.ts` | `POST /api/github/create-repo` — creates a GitHub repo, writes starter files, logs to `agent_activity_logs` |
| `HANDOFF_github-repo-backend.md` | This file |

## Files Modified

| File | Change |
|---|---|
| _(none)_ | No existing files were modified |

> `.env.example` already contained `GITHUB_PERSONAL_ACCESS_TOKEN=` and `GITHUB_DEFAULT_OWNER=` from a prior session — no change needed.

---

## API Route Added

### `POST /api/github/create-repo`

**Request body:**
```json
{
  "businessId": "<uuid>",
  "repoName": "optional-override",
  "visibility": "private",
  "includeStarterFiles": true
}
```

- `repoName` is optional; defaults to the business `idea_name`, sanitized.
- `visibility` defaults to `"private"`.
- `includeStarterFiles` defaults to `true`.

**Success response (201):**
```json
{
  "ok": true,
  "data": {
    "repoUrl": "https://github.com/owner/repo-name",
    "fullName": "owner/repo-name",
    "owner": "owner",
    "name": "repo-name",
    "private": true,
    "activityLogId": "<uuid>"
  },
  "warning": "optional — present only if starter file creation failed"
}
```

**Error codes:**

| Code | HTTP | Meaning |
|---|---|---|
| `missing_supabase_env` | 503 | Supabase env vars absent |
| `missing_github_env` | 503 | `GITHUB_PERSONAL_ACCESS_TOKEN` not set |
| `invalid_input` | 400 | Bad request body or missing `businessId` |
| `unauthenticated` | 401 | No valid Supabase session |
| `forbidden` | 403 | Valid session but wrong owner |
| `business_not_found` | 404 | Business UUID not found |
| `github_permission_missing` | 403 | No GitHub tool permission record for this business |
| `github_not_approved` | 403 | GitHub permission exists but is not `approved` or `connected_demo` |
| `github_create_failed` | 500 | GitHub REST API returned an error |

If repo creation succeeds but starter file writes fail, the route returns `ok: true` with a `warning` field — the repo is created and the activity log is written.

---

## Env Vars Required

| Variable | Required | Description |
|---|---|---|
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Yes | Personal access token with `repo` scope (create, read, write) |
| `GITHUB_DEFAULT_OWNER` | No | GitHub username/org to create repos under. Defaults to the token owner if omitted. |

### How to Create the Token

1. GitHub → Settings → Developer settings → Personal access tokens → **Tokens (classic)**
2. Click **Generate new token (classic)**
3. Select scopes: `repo` (full control of private repositories)
4. Copy the token and add it to `.env.local`:
   ```
   GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
   GITHUB_DEFAULT_OWNER=your-github-username
   ```

> The token is **never** returned in any API response, logged to console, or exposed to the browser. All GitHub calls happen inside `src/lib/github/client.ts` (server-only).

---

## Safety Model

- **Repo creation is always explicit.** It only happens when a founder POSTs to `/api/github/create-repo`. There is no automatic repo creation during blueprint generation or tool seeding.
- **GitHub permission gate.** The route checks that a `github` tool permission exists for the business and has status `approved` or `connected_demo` before calling the API.
- **Default visibility is `private`.** A caller must explicitly pass `"visibility": "public"` to create a public repo.
- **Repo name sanitization.** The name is lowercased, stripped of non-alphanumeric characters (replaced with hyphens), and capped at 100 characters.
- **Token is server-only.** `getGitHubEnv()` is in `src/lib/github/env.ts` and only called from server-side code. It is never imported from any client component.
- **No service role key.** All Supabase writes use the user-scoped server client with RLS enforced.

---

## Where Repo Metadata Is Stored

Repo details are persisted in `agent_activity_logs.metadata` with `activity_type = "github_repo_created"`:

```json
{
  "githubRepoUrl": "https://github.com/owner/repo",
  "githubRepoFullName": "owner/repo",
  "githubRepoId": 123456789,
  "githubCloneUrl": "https://github.com/owner/repo.git",
  "githubOwner": "owner",
  "githubRepoName": "repo",
  "visibility": "private"
}
```

Read it back with `getLatestGitHubRepoForBusiness(businessId)` from `src/lib/github/repo-metadata.ts`.

The `tool_permissions` record for GitHub is updated to `connected_demo` / `connected_demo` after a successful repo creation. No `permissions` array modifications are needed — the status change is sufficient.

---

## Starter Files

When `includeStarterFiles: true` (default), these files are written to the new repo serially:

| Path | Content |
|---|---|
| `README.md` | Business name, one-line idea if available, "generated by bucks.ai", "Initial scaffold only" notice |
| `.gitignore` | Standard Node/Next.js ignore patterns |
| `package.json` | Minimal placeholder with `dev` script |
| `src/README.md` | Placeholder noting source will be generated later |

---

## Manual Test Steps

Requires: `.env.local` with real Supabase + GitHub credentials, `npm run dev` running, a valid session.

```bash
# 1. Logged-out POST returns 401
curl -X POST http://localhost:3000/api/github/create-repo \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>"}'
# → { ok: false, code: "unauthenticated" }

# 2. GitHub env not set returns 503
# (remove GITHUB_PERSONAL_ACCESS_TOKEN from .env.local temporarily)
curl -b <session-cookie> -X POST http://localhost:3000/api/github/create-repo \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>"}'
# → { ok: false, code: "missing_github_env" }

# 3. GitHub permission not approved returns 403
# (seed permissions but do NOT approve GitHub before this call)
curl -b <session-cookie> -X POST http://localhost:3000/api/github/create-repo \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>"}'
# → { ok: false, code: "github_not_approved" }

# 4. Approve GitHub permission first
curl -b <session-cookie> -X PATCH http://localhost:3000/api/tool-permissions/<permission-uuid> \
  -H "Content-Type: application/json" \
  -d '{"action":"approve"}'

# 5. Create repo — should return 201 with repoUrl
curl -b <session-cookie> -X POST http://localhost:3000/api/github/create-repo \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>","visibility":"private","includeStarterFiles":true}'
# → { ok: true, data: { repoUrl: "...", fullName: "...", ... } }

# 6. Verify on GitHub: repo exists, starter files are present
# 7. Check agent_activity_logs in Supabase: activity_type = "github_repo_created", metadata contains repo info
# 8. Check tool_permissions: GitHub row should now have status = "connected_demo"
```

---

## Known Limitations

- **One token, one owner.** Using a PAT means all repos are created under the token owner's account. Multi-tenant or per-user repo creation is not supported until OAuth or GitHub App is implemented.
- **No duplicate check.** If the caller hits the endpoint twice with the same repo name, the second call will fail with a `github_create_failed` (GitHub returns 422 Unprocessable Entity for duplicate names). Handle this at the UI layer or check activity logs before calling.
- **No deletion.** There is no API route to delete a repo. This is intentional — deletion is destructive and requires explicit manual action.
- **Starter files are best-effort.** If a starter file write fails mid-way (e.g. rate limit), some files may be written and others not. The route returns a `warning` but does not roll back the repo.

---

## What Is Intentionally Deferred

- **GitHub OAuth / GitHub App** — proper per-user auth for multi-tenant repo creation. Current PAT is dev/demo only.
- **Real code generation** — the starter repo is a scaffold. No agent writes actual application code yet.
- **Repo update / push automation** — committing generated code, opening PRs, etc.
- **Vercel deployment** — triggering a deploy from the created repo.
- **Webhook listener** — reacting to GitHub events (push, PR merge) in bucks.ai.

---

## Recommended Next Task

**Branch: `feature/github-repo-ui`**

Wire a "Create Repository" button into the business detail page or tools panel:

1. Read the current GitHub tool permission status — show a "Approve GitHub" CTA if not yet approved.
2. Once approved, show a "Create Repository" button that POSTs to `/api/github/create-repo`.
3. On success, display the `repoUrl` as a link and render the `activityLogId` in the activity feed.
4. If a repo already exists (check via `getLatestGitHubRepoForBusiness`), show the existing repo link instead of the create button.
