import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { hasVercelEnv } from "@/lib/vercel/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { getLatestVercelProjectForBusiness } from "@/lib/vercel/project-metadata";
import { refreshVercelDeploymentStatusForBusiness } from "@/lib/vercel/deployment-status";
import { badRequest, zodIssuesToFields } from "@/lib/api-error";
import { refreshVercelDeploymentStatusBodySchema } from "@/lib/schemas/infra";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// POST /api/vercel/refresh-deployment-status
// Body: { businessId: string }
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return errorResponse(
      "Supabase is not configured.",
      "missing_supabase_env",
      503
    );
  }

  // Parse body
  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = refreshVercelDeploymentStatusBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const { businessId } = parsed.data;

  // Auth
  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:vercel-refresh-status`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  // Business ownership
  const businessResult = await getBusinessById(businessId);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }
  const business = businessResult.data;
  if (business.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  // Require existing Vercel project metadata
  const metaResult = await getLatestVercelProjectForBusiness(businessId);
  if (metaResult.error || !metaResult.data) {
    return errorResponse(
      "No Vercel project found for this business. Create a Vercel project first.",
      "vercel_project_missing",
      400
    );
  }

  // If token is missing, log and return the stored state with a clear warning
  if (!hasVercelEnv()) {
    const stored = metaResult.data;
    return Response.json({
      ok: true,
      data: {
        status: "manual_action_required",
        deploymentUrl: stored.vercelDeploymentUrl ?? null,
        deploymentId: null,
        environment: "unknown",
        warnings: [
          "VERCEL_TOKEN is not configured. Add it to .env.local to enable live status checks.",
        ],
      },
    });
  }

  // Refresh deployment status
  const refreshResult = await refreshVercelDeploymentStatusForBusiness(
    businessId,
    user.id
  );

  if (refreshResult.error || !refreshResult.data) {
    return errorResponse(
      refreshResult.error ?? "Deployment status refresh failed.",
      "vercel_status_failed",
      500
    );
  }

  return Response.json({
    ok: true,
    data: refreshResult.data,
  });
}
