import { hasSupabaseEnv } from "@/lib/supabase/env";
import { requireUser } from "@/lib/api-auth";
import { getPendingApprovalsForOwner } from "@/lib/approvals";
import { apiError } from "@/lib/api-error";

// ---------------------------------------------------------------------------
// GET /api/approvals
// Lists the authenticated owner's pending in-app approval requests (mirrors
// the runner's outbox/ approval gates — see supabase/m4a-approvals-queue.sql
// and runner/langgraph/app_approvals_daemon.py). Not business-scoped.
// ---------------------------------------------------------------------------

export async function GET() {
  if (!hasSupabaseEnv()) {
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { user, response } = await requireUser();
  if (!user) return response;

  const result = await getPendingApprovalsForOwner(user.id);
  if (result.error || !result.data) {
    if (result.code === "approvals_schema_missing") {
      return Response.json({ ok: true, data: { approvals: [] } });
    }
    return apiError(result.error ?? "Could not load approvals.", result.code ?? "approvals_fetch_failed", 500);
  }

  return Response.json({ ok: true, data: { approvals: result.data } });
}
