// POST /api/businesses/[id]/agent-runs/infer
// Back-fills agent runs from existing agent_activity_logs.
// Idempotent: skips activity logs already referenced by an existing run.
//
// Response shapes:
//   success: { ok: true, data: { created: number, skipped: number } }
//   error:   { ok: false, code: string, error: string }
//
// Error codes:
//   unauthenticated            — no session
//   forbidden                  — wrong owner
//   business_not_found         — business does not exist
//   agent_runs_schema_missing  — agent_runs table not yet applied
//   agent_runs_infer_failed    — inference process failed

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { inferAgentRunsFromActivityLogs } from "@/lib/agents/runs";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return errorResponse("Supabase is not configured.", "missing_supabase_env", 503);
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
    return errorResponse("Business not found.", "business_not_found", 404);
  }

  if (businessResult.data.user_id !== userResult.data.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  const result = await inferAgentRunsFromActivityLogs(id);

  if (result.error || !result.data) {
    const code = result.code ?? "agent_runs_infer_failed";
    const httpStatus = code === "agent_runs_schema_missing" ? 503 : 500;
    return errorResponse(
      result.error ?? "Inference failed.",
      code,
      httpStatus
    );
  }

  return Response.json({ ok: true, data: result.data });
}
