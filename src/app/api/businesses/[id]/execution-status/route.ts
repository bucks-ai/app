import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { getBusinessExecutionStatus } from "@/lib/execution/status";
import { apiError, badRequest, notFound } from "@/lib/api-error";

// ---------------------------------------------------------------------------
// GET /api/businesses/[id]/execution-status
// ---------------------------------------------------------------------------

export async function GET(
  _request: Request,
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
    return badRequest("Business id is required.", "invalid_input");
  }

  const { user, response } = await requireUser();
  if (!user) return response;

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return notFound("Business not found.", "not_found");
  }

  if (businessResult.data.user_id !== user.id) {
    return apiError("Access denied.", "forbidden", 403);
  }

  const statusResult = await getBusinessExecutionStatus(id);
  if (statusResult.error || !statusResult.data) {
    return apiError(
      statusResult.error ?? "Could not build execution status.",
      "execution_status_failed",
      500
    );
  }

  return Response.json({
    ok: true,
    data: statusResult.data,
  });
}
