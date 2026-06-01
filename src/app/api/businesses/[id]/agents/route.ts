// GET /api/businesses/[id]/agents
// Returns the full agent registry view for a business.
//
// Response shape:
//   { ok: true, data: { summary, nodes, agents } }
//   { ok: false, code: string, error: string }
//
// Error codes:
//   unauthenticated    — no session
//   forbidden          — wrong owner
//   business_not_found — business does not exist
//   agent_registry_unavailable — registry could not be built

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { getAgentRegistryForBusiness } from "@/lib/agents/status";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

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
    return errorResponse("Business not found.", "business_not_found", 404);
  }

  if (businessResult.data.user_id !== userResult.data.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  const registryResult = await getAgentRegistryForBusiness(id);
  if (registryResult.error || !registryResult.data) {
    return errorResponse(
      registryResult.error ?? "Could not build agent registry.",
      registryResult.code ?? "agent_registry_unavailable",
      500
    );
  }

  return Response.json({
    ok: true,
    data: {
      summary: registryResult.data.summary,
      nodes: registryResult.data.nodes,
      agents: registryResult.data.agents,
    },
  });
}
