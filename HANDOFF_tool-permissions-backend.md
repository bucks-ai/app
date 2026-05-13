# Handoff: tool-permissions-backend

Branch: `feature/tool-permissions-backend`
Date: 2026-05-13

---

## Files Created

| File | Purpose |
|---|---|
| `src/types/tool-permissions.ts` | All tool-permission types: statuses, setup statuses, actions, view shape, update input, seed result, and the action→status transition map |
| `src/lib/tool-permissions.ts` | Server-side helper functions for reading, seeding, updating, and logging tool permissions |
| `src/app/api/tool-permissions/route.ts` | `GET` (list with canSeed flag) and `POST` (seed) for `/api/tool-permissions` |
| `src/app/api/tool-permissions/[id]/route.ts` | `PATCH` for `/api/tool-permissions/[id]` — applies a state-machine action |
| `HANDOFF_tool-permissions-backend.md` | This file |

## Files Modified

| File | Change |
|---|---|
| `src/app/api/businesses/save-blueprint/route.ts` | After blueprint + human actions are saved, calls `seedToolPermissionsForBusiness`. Seed failure is soft — blueprint save succeeds but a `toolPermissionWarning` field appears in the response body. Also creates an `agent_activity_logs` entry for the seed event. |

No other existing files were modified.

---

## API Routes Added

### `GET /api/tool-permissions?businessId=<uuid>`

Returns existing tool permission records for a business. Does **not** auto-seed.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "permissions": [ ...ToolPermissionView[] ],
    "canSeed": true
  }
}
```

`canSeed` is `true` when `permissions` is empty — a hint to the frontend to offer a "Set up tools" action.

---

### `POST /api/tool-permissions`

Seeds default tool permissions from `src/lib/tool-registry.ts`. Idempotent: tools that already exist for the business are skipped.

**Request body:**
```json
{ "businessId": "<uuid>" }
```

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "seeded": 15,
    "skipped": 0,
    "records": [ ...ToolPermissionView[] ]
  }
}
```

---

### `PATCH /api/tool-permissions/[id]`

Applies a state-machine action to a specific tool permission.

**Request body:**
```json
{ "action": "approve" }
```

**Valid actions:**

| Action | New `status` | New `setup_status` |
|---|---|---|
| `request_approval` | `approval_requested` | `awaiting_founder_approval` |
| `approve` | `approved` | `ready_to_connect` |
| `mark_human_required` | `human_required` | `awaiting_human_legal_step` |
| `mark_connected_demo` | `connected_demo` | `connected_demo` |
| `reject` | `rejected` | `rejected` |
| `block` | `blocked` | `blocked` |
| `reset` | `not_connected` | `not_started` |

**Response (200):**
```json
{
  "ok": true,
  "data": { ...ToolPermissionView }
}
```

A `agent_activity_logs` row is created for every successful PATCH (fire-and-forget; PATCH does not fail if the log write fails).

---

## Helper Functions Added (`src/lib/tool-permissions.ts`)

| Function | Description |
|---|---|
| `getToolPermissionsForBusiness(businessId)` | Returns all tool permissions for a business (ordered by creation time) |
| `getToolPermissionById(id)` | Returns a single tool permission by its UUID |
| `seedToolPermissionsForBusiness(businessId, userId)` | Seeds tools from the registry that are not yet present; idempotent |
| `updateToolPermissionStatus(input)` | Applies an `ACTION_STATUS_MAP` transition and persists the result |
| `getToolPermissionSummaryForBusiness(businessId)` | Returns aggregate counts by status and risk level |
| `createToolPermissionActivityLog(input)` | Writes a row to `agent_activity_logs` |

---

## Permission Status Model

### `ToolPermissionStatus`
```
not_connected → approval_requested → approved → connected_demo
not_connected → human_required     → approved_by_founder → connected_demo
not_connected → rejected
not_connected → blocked
```

### `ToolSetupStatus`
```
not_started → awaiting_founder_approval → ready_to_connect → connected_demo
not_started → awaiting_human_legal_step  → ready_to_connect → connected_demo
not_started → awaiting_identity_or_payment → ready_to_connect → connected_demo
not_started → rejected
not_started → blocked
```

---

## Seed Defaults (Preferred Tools)

| Tool | Initial `status` | Initial `setup_status` |
|---|---|---|
| GitHub | `approval_requested` | `awaiting_founder_approval` |
| Vercel | `approval_requested` | `awaiting_founder_approval` |
| Supabase | `connected_demo` | `connected_demo` |
| Stripe | `human_required` | `awaiting_identity_or_payment` |
| PostHog | `approval_requested` | `awaiting_founder_approval` |
| Gmail / Google Workspace | `human_required` | `awaiting_human_legal_step` |
| Airtable | `approval_requested` | `awaiting_founder_approval` |
| Resend | `approval_requested` | `awaiting_founder_approval` |
| OpenAI | `approval_requested` | `awaiting_identity_or_payment` |
| Anthropic | `approval_requested` | `awaiting_identity_or_payment` |
| Firecrawl | `approval_requested` | `awaiting_founder_approval` |
| Sentry | `approval_requested` | `awaiting_founder_approval` |
| Cloudflare | `human_required` | `awaiting_human_legal_step` |
| Clerk | `approval_requested` | `awaiting_founder_approval` |
| E2B / Docker Sandbox | `approval_requested` | `awaiting_founder_approval` |

All remaining tools from the extended registry fall back to rule-based defaults: tools with `requiresIdentityVerification` or `riskLevel=Critical`+`requiresPaymentSetup` → `human_required`; tools with `status=Blocked` → `blocked`; everything else → `approval_requested`.

---

## Security / Ownership Rules

- Every route requires a valid Supabase session (`getCurrentUser()`).
- Every business-scoped read/write verifies `businesses.user_id = auth.uid()` before proceeding.
- The `PATCH` route additionally checks `tool_permissions.user_id = auth.uid()` on the specific record.
- No `SUPABASE_SERVICE_ROLE_KEY` is used anywhere — all operations use the user-scoped server client with RLS enforced.
- No external tool calls, no real GitHub/Vercel/Stripe actions, no money movement, no email sending.

---

## Error Response Format

```json
{ "ok": false, "code": "<code>", "error": "<human-readable message>" }
```

| Code | HTTP Status | Meaning |
|---|---|---|
| `missing_supabase_env` | 503 | Supabase env vars absent |
| `unauthenticated` | 401 | No valid session |
| `forbidden` | 403 | Valid session but wrong owner |
| `not_found` | 404 | Business or permission not found |
| `invalid_input` | 400 | Bad request body or query params |
| `update_failed` | 500 | DB update failed |
| `seed_failed` | 500 | DB seed insert failed |

---

## How to Test APIs (manual)

Requires: `.env.local` with real Supabase credentials, a running dev server (`npm run dev`), and a valid Supabase session cookie (sign in via `/login` first).

```bash
# 1. Logged-out GET should return 401
curl http://localhost:3000/api/tool-permissions?businessId=<uuid>
# → { ok: false, code: "unauthenticated" }

# 2. Logged-in GET with no seeds yet → canSeed: true
curl -b <session-cookie> http://localhost:3000/api/tool-permissions?businessId=<uuid>
# → { ok: true, data: { permissions: [], canSeed: true } }

# 3. Logged-in POST seeds permissions
curl -b <session-cookie> -X POST http://localhost:3000/api/tool-permissions \
  -H "Content-Type: application/json" \
  -d '{"businessId":"<uuid>"}'
# → { ok: true, data: { seeded: N, skipped: 0, records: [...] } }

# 4. Logged-in PATCH updates status
curl -b <session-cookie> -X PATCH http://localhost:3000/api/tool-permissions/<permission-uuid> \
  -H "Content-Type: application/json" \
  -d '{"action":"approve"}'
# → { ok: true, data: { status: "approved", setup_status: "ready_to_connect", ... } }

# 5. Wrong businessId returns forbidden
curl -b <session-cookie> http://localhost:3000/api/tool-permissions?businessId=<other-users-uuid>
# → { ok: false, code: "forbidden" }

# 6. Blueprint save seeds automatically
curl -b <session-cookie> -X POST http://localhost:3000/api/businesses/save-blueprint \
  -H "Content-Type: application/json" \
  -d '{ "startupIdea": {...}, "blueprint": {...} }'
# → { ok: true, businessId: "...", detailUrl: "...", toolPermissionWarning?: "..." }
```

---

## What Is Intentionally Demo-Only

- `connected_demo` is a fake "fully connected" state used to simulate Supabase being pre-wired. No real OAuth or API key exchange happens.
- The seed logic is static — it does not detect whether a real integration is live (e.g. checking for an active `OPENAI_API_KEY` env var). All seeding uses predetermined defaults.
- `approved_by_founder` status is modelled in types but not yet reachable via any API action. It's reserved for a future "founder approval" webhook flow.

---

## Known Limitations

- The `tool_permissions` table uses a `(user_id, tool_id)` upsert conflict key in `upsertToolPermission` (projects.ts), but the new `seedToolPermissionsForBusiness` uses `business_id + tool_id` existence checks instead. If the schema gains a `(business_id, tool_id)` unique constraint, the seed can be simplified to a single upsert.
- `getToolPermissionSummaryForBusiness` is a helper available to future dashboard routes but not yet exposed via any API route.
- No pagination on `getToolPermissionsForBusiness` — safe for now (registry has ~30 tools).

---

## Recommended Next Task

**Branch: `feature/tool-permissions-ui`**

Wire the frontend `/tools` page (or a new `/dashboard/businesses/[id]/tools` sub-page) to the new API:

1. On load, `GET /api/tool-permissions?businessId=<id>` — if `canSeed: true`, show a "Set up tools" CTA that calls `POST /api/tool-permissions`.
2. Render each `ToolPermissionView` as a card with its `status` badge.
3. Add per-card action buttons that call `PATCH /api/tool-permissions/[id]` with the appropriate action.
4. Show the Operator Console status colors: indigo for `approval_requested`/`approved`, amber for `human_required`, green for `connected_demo`, red for `rejected`/`blocked`.
