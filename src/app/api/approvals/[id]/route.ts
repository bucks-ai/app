import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { requireUser } from "@/lib/api-auth";
import { updateApprovalDecision } from "@/lib/approvals";
import { apiError, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import { updateApprovalBodySchema } from "@/lib/schemas/infra";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

// ---------------------------------------------------------------------------
// PATCH /api/approvals/[id]
// Records a founder's Approve/Reject decision on a pending approval request.
// Idempotent with re-clicks and with the Slack daemon: the decision only
// takes effect while the row is still "pending" (see updateApprovalDecision).
// The runner's app_approvals_daemon.py separately polls decided rows and
// writes the actual inbox/ fulfillment file (with its own existence check).
// ---------------------------------------------------------------------------

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { id } = await params;
  if (!id) {
    return badRequest("Approval id is required.", "invalid_input");
  }

  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:approvals-update`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateApprovalBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest("Request body failed validation.", "validation_error", zodIssuesToFields(parsed.error));
  }

  const result = await updateApprovalDecision({
    id,
    action: parsed.data.action,
    userId: user.id,
    decidedBy: user.email ?? user.id,
  });

  if (result.error || !result.data) {
    if (result.code === "not_found") {
      return notFound("Approval not found.", "not_found");
    }
    if (result.code === "forbidden") {
      return apiError("Access denied.", "forbidden", 403);
    }
    return apiError(result.error ?? "Update failed.", result.code ?? "approval_update_failed", 500);
  }

  return Response.json({ ok: true, data: result.data });
}
