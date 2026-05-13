import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser } from "@/lib/projects";
import {
  getToolPermissionById,
  updateToolPermissionStatus,
  createToolPermissionActivityLog,
} from "@/lib/tool-permissions";
import type { ToolPermissionAction } from "@/types/tool-permissions";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

const VALID_ACTIONS: ToolPermissionAction[] = [
  "request_approval",
  "approve",
  "mark_human_required",
  "mark_connected_demo",
  "reject",
  "block",
  "reset",
];

function isValidAction(value: unknown): value is ToolPermissionAction {
  return typeof value === "string" && (VALID_ACTIONS as string[]).includes(value);
}

// ---------------------------------------------------------------------------
// PATCH /api/tool-permissions/[id]
// Applies a state-machine action to a tool permission record.
// ---------------------------------------------------------------------------

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return errorResponse(
      "Supabase is not configured.",
      "missing_supabase_env",
      503
    );
  }

  const { id } = await params;
  if (!id) {
    return errorResponse("Permission id is required.", "invalid_input", 400);
  }

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return errorResponse("Authentication required.", "unauthenticated", 401);
  }

  const user = userResult.data;

  let body: { action?: unknown };
  try {
    body = (await request.json()) as { action?: unknown };
  } catch {
    return errorResponse("Request body must be valid JSON.", "invalid_input", 400);
  }

  if (!isValidAction(body.action)) {
    return errorResponse(
      `action must be one of: ${VALID_ACTIONS.join(", ")}.`,
      "invalid_input",
      400
    );
  }

  const action = body.action;

  // Fetch the record so we know the business_id for the activity log
  const fetchResult = await getToolPermissionById(id);
  if (fetchResult.error || !fetchResult.data) {
    return errorResponse("Tool permission not found.", "not_found", 404);
  }

  const existing = fetchResult.data;
  if (existing.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  const updateResult = await updateToolPermissionStatus({
    id,
    action,
    userId: user.id,
  });

  if (updateResult.error || !updateResult.data) {
    return errorResponse(
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
