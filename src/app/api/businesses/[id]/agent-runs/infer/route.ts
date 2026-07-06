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
import { badRequest, zodIssuesToFields } from "@/lib/api-error";
import { agentRunsInferParamsSchema } from "@/lib/schemas/infra";
import { limit, tooManyRequests, type RateLimitOptions } from "@/lib/rate-limit";

/** Conservative default: agent-run inference is an expensive AI-adjacent operation. */
const AGENT_RUNS_INFER_RATE_LIMIT: RateLimitOptions = { limit: 5, windowMs: 60_000 };

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

  const rateLimitResult = await limit(`${user.id}:agent-runs-infer`, AGENT_RUNS_INFER_RATE_LIMIT);
  if (!rateLimitResult.allowed) return tooManyRequests();

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }

  if (businessResult.data.user_id !== user.id) {
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
