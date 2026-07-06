import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { hasVercelEnv } from "@/lib/vercel/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { getLatestVercelProjectForBusiness } from "@/lib/vercel/project-metadata";
import {
  getLatestVercelDeploymentForProject,
  normalizeVercelDeploymentStatus,
  normalizeVercelDeploymentEnvironment,
  extractDeploymentUrl,
} from "@/lib/vercel/deployment-status";

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
  const { user, response } = await requireUser();
  if (!user) return response;

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
        project: null,
        latestDeployment: null,
        storedMetadata: { deploymentUrl: null },
        warnings: [],
      },
    });
  }

  const meta = metaResult.data;
  const warnings: string[] = meta.warnings ? [...meta.warnings] : [];

  const project = {
    projectId: meta.vercelProjectId,
    projectName: meta.vercelProjectName,
    dashboardUrl: meta.vercelDashboardUrl,
    gitRepoFullName: meta.gitRepoFullName ?? null,
    productionBranch: meta.productionBranch ?? null,
    createdAt: meta.createdAt,
  };

  const storedMetadata = {
    deploymentUrl: meta.vercelDeploymentUrl ?? null,
  };

  // Fetch latest deployment from Vercel API if token is available
  let latestDeployment = null;

  if (!hasVercelEnv()) {
    warnings.push("VERCEL_TOKEN not set — showing stored metadata only.");
  } else {
    const { deployment, warnings: fetchWarnings } =
      await getLatestVercelDeploymentForProject({
        projectId: meta.vercelProjectId,
      });

    warnings.push(...fetchWarnings);

    if (deployment) {
      const status = normalizeVercelDeploymentStatus(deployment.state);
      const environment = normalizeVercelDeploymentEnvironment(deployment.target);
      const deploymentUrl = status === "ready" ? extractDeploymentUrl(deployment) : null;

      latestDeployment = {
        status,
        deploymentUrl,
        deploymentId: deployment.uid,
        environment,
        createdAt: deployment.createdAt
          ? new Date(deployment.createdAt).toISOString()
          : null,
        readyAt: deployment.readyAt
          ? new Date(deployment.readyAt).toISOString()
          : null,
      };
    }
  }

  return Response.json({
    ok: true,
    data: {
      project,
      latestDeployment,
      storedMetadata,
      warnings,
    },
  });
}
