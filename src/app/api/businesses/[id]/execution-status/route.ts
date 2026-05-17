import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById, getCurrentUser } from "@/lib/projects";
import { getBusinessExecutionStatus } from "@/lib/execution/status";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// GET /api/businesses/[id]/execution-status
// ---------------------------------------------------------------------------

export async function GET(
  _request: Request,
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
    return errorResponse("Business id is required.", "invalid_input", 400);
  }

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return errorResponse("Authentication required.", "unauthenticated", 401);
  }

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "not_found", 404);
  }

  if (businessResult.data.user_id !== userResult.data.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  const statusResult = await getBusinessExecutionStatus(id);
  if (statusResult.error || !statusResult.data) {
    return errorResponse(
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
