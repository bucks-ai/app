import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { hasVercelEnv } from "@/lib/vercel/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { getLatestVercelProjectForBusiness } from "@/lib/vercel/project-metadata";
import { listVercelDeployments } from "@/lib/vercel/client";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// GET /api/vercel/project-status?businessId=...
// ---------------------------------------------------------------------------

export async function GET(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return errorResponse(
      "Supabase is not configured.",
      "missing_supabase_env",
      503
    );
  }

  const { searchParams } = new URL(request.url);
  const businessId = searchParams.get("businessId");
  if (!businessId) {
    return errorResponse("businessId query param is required.", "invalid_input", 400);
  }

  // Auth
  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return errorResponse("Authentication required.", "unauthenticated", 401);
  }
  const user = userResult.data;

  // Business ownership
  const businessResult = await getBusinessById(businessId);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }
  const business = businessResult.data;
  if (business.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  // Read stored Vercel project metadata
  const metaResult = await getLatestVercelProjectForBusiness(businessId);
  if (metaResult.error || !metaResult.data) {
    return Response.json({
      ok: true,
      data: {
        vercelProject: null,
        deployments: [],
      },
    });
  }

  const meta = metaResult.data;
  const warnings: string[] = meta.warnings ? [...meta.warnings] : [];

  // Optionally fetch live deployments from Vercel API
  let deployments: unknown[] = [];
  if (hasVercelEnv() && meta.vercelProjectId) {
    try {
      deployments = await listVercelDeployments({
        projectId: meta.vercelProjectId,
        limit: 5,
      });
    } catch (e) {
      warnings.push(
        `Could not fetch live deployments: ${e instanceof Error ? e.message : String(e)}`
      );
    }
  } else if (!hasVercelEnv()) {
    warnings.push("VERCEL_TOKEN not set — showing stored metadata only.");
  }

  return Response.json({
    ok: true,
    data: {
      vercelProject: {
        projectId: meta.vercelProjectId,
        projectName: meta.vercelProjectName,
        dashboardUrl: meta.vercelDashboardUrl,
        deploymentUrl: meta.vercelDeploymentUrl ?? null,
        gitRepoFullName: meta.gitRepoFullName ?? null,
        productionBranch: meta.productionBranch ?? null,
        createdAt: meta.createdAt,
      },
      deployments,
      ...(warnings.length > 0 ? { warnings } : {}),
    },
  });
}
