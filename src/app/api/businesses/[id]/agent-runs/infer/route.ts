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
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { inferAgentRunsFromActivityLogs } from "@/lib/agents/runs";
import { apiError, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import { agentRunsInferParamsSchema } from "@/lib/schemas/infra";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const rawParams = await params;
  const parsed = agentRunsInferParamsSchema.safeParse(rawParams);
  if (!parsed.success) {
    return badRequest(
      "Request path failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const { id } = parsed.data;

  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:agent-runs-infer`, RATE_LIMITS.agentRunsInfer);
  if (!rateLimitResult.allowed) return tooManyRequests();

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return notFound("Business not found.", "business_not_found");
  }

  if (businessResult.data.user_id !== user.id) {
    return apiError("Access denied.", "forbidden", 403);
  }

  const result = await inferAgentRunsFromActivityLogs(id);

  if (result.error || !result.data) {
    const code = result.code ?? "agent_runs_infer_failed";
    const httpStatus = code === "agent_runs_schema_missing" ? 503 : 500;
    return apiError(
      result.error ?? "Inference failed.",
      code,
      httpStatus
    );
  }

  return Response.json({ ok: true, data: result.data });
}
