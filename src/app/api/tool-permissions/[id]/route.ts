import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { requireUser } from "@/lib/api-auth";
import {
  getToolPermissionById,
  updateToolPermissionStatus,
  createToolPermissionActivityLog,
} from "@/lib/tool-permissions";
import { apiError, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import { updateToolPermissionBodySchema } from "@/lib/schemas/infra";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

// ---------------------------------------------------------------------------
// PATCH /api/tool-permissions/[id]
// Applies a state-machine action to a tool permission record.
// ---------------------------------------------------------------------------

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return apiError(
      "Supabase is not configured.",
      "missing_supabase_env",
      503
    );
  }

  const { id } = await params;
  if (!id) {
    return badRequest("Permission id is required.", "invalid_input");
  }

  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:tool-permissions-update`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateToolPermissionBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const { action } = parsed.data;

  // Fetch the record so we know the business_id for the activity log
  const fetchResult = await getToolPermissionById(id);
  if (fetchResult.error || !fetchResult.data) {
    return notFound("Tool permission not found.", "not_found");
  }

  const existing = fetchResult.data;
  if (existing.user_id !== user.id) {
    return apiError("Access denied.", "forbidden", 403);
  }

  const updateResult = await updateToolPermissionStatus({
    id,
    action,
    userId: user.id,
  });

  if (updateResult.error || !updateResult.data) {
    return apiError(
      updateResult.error ?? "Update failed.",
      "update_failed",
      500
    );
  }

  const updated = updateResult.data;

  // Fire-and-forget activity log — do not fail PATCH if log fails
  if (existing.business_id) {
    createToolPermissionActivityLog({
      business_id: existing.business_id,
      user_id: user.id,
      activity_type: "tool_permission_updated",
      message: `Tool permission for ${existing.tool_name} updated via action "${action}". New status: ${updated.status}.`,
      metadata: {
        tool_id: existing.tool_id,
        tool_name: existing.tool_name,
        previous_status: existing.status,
        new_status: updated.status,
        action,
      },
    }).catch(() => undefined);
  }

  return Response.json({ ok: true, data: updated });
}
