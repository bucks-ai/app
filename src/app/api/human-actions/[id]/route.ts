import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { requireUser } from "@/lib/api-auth";
import { updateHumanActionDecision } from "@/lib/human-actions";
import { createAgentActivityLog } from "@/lib/projects";
import { apiError, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import { updateHumanActionBodySchema } from "@/lib/schemas/infra";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

// ---------------------------------------------------------------------------
// PATCH /api/human-actions/[id]
// Records the founder's Approve/Dismiss decision on a human_required_actions
// row — the founder-owned steps bucks.ai cannot take itself (register the
// business, open a bank account, grant a data permission).
// Idempotent with re-clicks: updateHumanActionDecision returns an
// already-decided row untouched.
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
    return badRequest("Human action id is required.", "invalid_input");
  }

  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(
    `${user.id}:human-actions-update`,
    RATE_LIMITS.mutationDefault
  );
  if (!rateLimitResult.allowed) return tooManyRequests();

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateHumanActionBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error)
    );
  }

  const result = await updateHumanActionDecision({
    id,
    decision: parsed.data.action,
    userId: user.id,
  });

  if (result.error || !result.data) {
    if (result.code === "not_found") {
      return notFound("Human action not found.", "not_found");
    }
    if (result.code === "forbidden") {
      return apiError("Access denied.", "forbidden", 403);
    }
    return apiError(
      result.error ?? "Update failed.",
      result.code ?? "human_action_update_failed",
      500
    );
  }

  const updated = result.data;

  // Fire-and-forget audit trail — a failed log must not fail the decision.
  createAgentActivityLog({
    business_id: updated.business_id,
    user_id: user.id,
    activity_type: "human_action_decided",
    message: `Founder ${parsed.data.action === "approve" ? "approved" : "dismissed"} "${updated.title}".`,
    metadata: {
      human_action_id: updated.id,
      decision: parsed.data.action,
      new_status: updated.status,
      risk_level: updated.risk_level,
    },
  }).catch(() => undefined);

  return Response.json({ ok: true, data: updated });
}
