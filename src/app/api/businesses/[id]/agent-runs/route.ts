// GET  /api/businesses/[id]/agent-runs — list agent runs + summary
// POST /api/businesses/[id]/agent-runs — create a new agent run
//
// Response shapes:
//   GET  success: { ok: true, data: { summary, runs } }
//   POST success: { ok: true, data: AgentRunRecord }
//   error:        { ok: false, code: string, error: string }
//
// Error codes:
//   unauthenticated            — no session
//   forbidden                  — wrong owner
//   business_not_found         — business does not exist
//   invalid_input              — missing or malformed body
//   agent_runs_schema_missing  — agent_runs table not yet applied
//   agent_run_create_failed    — DB write failed

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import {
  getAgentRunsForBusiness,
  getAgentRunSummaryForBusiness,
  createAgentRun,
} from "@/lib/agents/runs";
import type { AgentRunCreateInput } from "@/types/agent-runs";
import type { AgentTemplateId, AgentNodeId } from "@/types/agents";
import { getAgentTemplate } from "@/lib/agents/registry";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

export async function GET(
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

  const { user, response } = await requireUser();
  if (!user) return response;

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }

  if (businessResult.data.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  const [runsResult, summaryResult] = await Promise.all([
    getAgentRunsForBusiness(id),
    getAgentRunSummaryForBusiness(id),
  ]);

  // Schema missing is non-fatal — return empty
  if (
    runsResult.code === "agent_runs_schema_missing" ||
    summaryResult.code === "agent_runs_schema_missing"
  ) {
    return Response.json({
      ok: true,
      data: {
        summary: summaryResult.data ?? {
          businessId: id,
          totalRuns: 0,
          completedRuns: 0,
          failedRuns: 0,
          runningRuns: 0,
          blockedRuns: 0,
          waitingRuns: 0,
          lastRunAt: null,
          agentsCovered: [],
          generatedAt: new Date().toISOString(),
        },
        runs: [],
        _warning: "agent_runs table not yet applied",
      },
    });
  }

  if (runsResult.error || !runsResult.data) {
    return errorResponse(
      runsResult.error ?? "Could not load agent runs.",
      runsResult.code ?? "agent_runs_fetch_failed",
      500
    );
  }

  if (summaryResult.error || !summaryResult.data) {
    return errorResponse(
      summaryResult.error ?? "Could not build agent runs summary.",
      summaryResult.code ?? "agent_runs_fetch_failed",
      500
    );
  }

  return Response.json({
    ok: true,
    data: {
      summary: summaryResult.data,
      runs: runsResult.data,
    },
  });
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return errorResponse("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { id } = await params;
  if (!id) {
    return errorResponse("Business id is required.", "invalid_input", 400);
  }

  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:agent-runs`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }

  if (businessResult.data.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return errorResponse("Invalid JSON body.", "invalid_input", 400);
  }

  const agentId = body.agentId as string | undefined;
  if (!agentId) {
    return errorResponse("agentId is required.", "invalid_input", 400);
  }

  const title = body.title as string | undefined;
  if (!title) {
    return errorResponse("title is required.", "invalid_input", 400);
  }

  // Resolve node_id from agent registry
  const template = getAgentTemplate(agentId as AgentTemplateId);
  if (!template) {
    return errorResponse(`Unknown agent id: ${agentId}`, "invalid_input", 400);
  }

  const input: AgentRunCreateInput = {
    business_id: id,
    user_id: user.id,
    agent_id: agentId as AgentTemplateId,
    node_id: template.node as AgentNodeId,
    title,
    summary: (body.summary as string) ?? null,
    status: (body.status as AgentRunCreateInput["status"]) ?? "completed",
    source: (body.source as AgentRunCreateInput["source"]) ?? "user_triggered",
    trigger: (body.trigger as AgentRunCreateInput["trigger"]) ?? null,
    input: (body.input as Record<string, unknown>) ?? {},
    output: (body.output as Record<string, unknown>) ?? {},
    artifacts: (body.artifacts as AgentRunCreateInput["artifacts"]) ?? [],
    error: (body.error as AgentRunCreateInput["error"]) ?? null,
  };

  const result = await createAgentRun(input);

  if (result.error || !result.data) {
    const code = result.code ?? "agent_run_create_failed";
    const httpStatus = code === "agent_runs_schema_missing" ? 503 : 500;
    return errorResponse(
      result.error ?? "Failed to create agent run.",
      code,
      httpStatus
    );
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}
