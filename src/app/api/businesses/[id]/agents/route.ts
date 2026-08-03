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
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { getAgentRegistryForBusiness } from "@/lib/agents/status";
import { apiError, badRequest, notFound } from "@/lib/api-error";

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
    return notFound("Business not found.", "business_not_found");
  }

  if (businessResult.data.user_id !== user.id) {
    return apiError("Access denied.", "forbidden", 403);
  }

  const registryResult = await getAgentRegistryForBusiness(id);
  if (registryResult.error || !registryResult.data) {
    return apiError(
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
