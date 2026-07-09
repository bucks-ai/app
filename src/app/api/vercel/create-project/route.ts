import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { hasVercelEnv } from "@/lib/vercel/env";
import { getBusinessById, createAgentActivityLog } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { getToolPermissionsForBusiness, updateToolPermissionStatus } from "@/lib/tool-permissions";
import { getLatestGitHubRepoForBusiness } from "@/lib/github/repo-metadata";
import {
  prepareDeployableNextScaffold,
  ScaffoldPreparationError,
} from "@/lib/github/next-scaffold";
import { sanitizeVercelProjectName, createVercelProjectWithSetup } from "@/lib/vercel/client";
import { apiError, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import { createVercelProjectBodySchema } from "@/lib/schemas/infra";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";
import { capture } from "@/lib/analytics/server";

function scaffoldErrorResponse(error: unknown) {
  const detail =
    error instanceof ScaffoldPreparationError
      ? {
          ...(error.failedFile ? { failedFile: error.failedFile } : {}),
          ...(error.githubStatusCode
            ? { githubStatusCode: error.githubStatusCode }
            : {}),
          ...(error.safeDetail ? { githubMessage: error.safeDetail } : {}),
        }
      : undefined;

  return apiError(
    "Starter scaffold could not be written to GitHub.",
    "scaffold_failed",
    500,
    detail ? { detail } : undefined,
  );
}

// ---------------------------------------------------------------------------
// POST /api/vercel/create-project
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return apiError(
      "Supabase is not configured.",
      "missing_supabase_env",
      503
    );
  }

  if (!hasVercelEnv()) {
    return apiError(
      "Vercel token is not configured. Add VERCEL_TOKEN to .env.local.",
      "vercel_env_missing",
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

  const parsed = createVercelProjectBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const {
    businessId,
    projectName: requestedProjectName,
    prepareScaffold = false,
    createDeployment = false,
  } = parsed.data;

  // Auth
  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:vercel-create-project`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  // Business ownership
  const businessResult = await getBusinessById(businessId);
  if (businessResult.error || !businessResult.data) {
    return notFound("Business not found.", "business_not_found");
  }
  const business = businessResult.data;
  if (business.user_id !== user.id) {
    return apiError("Access denied.", "forbidden", 403);
  }

  // Vercel permission gate
  const permissionsResult = await getToolPermissionsForBusiness(businessId);
  if (permissionsResult.error || !permissionsResult.data) {
    return apiError(
      "Could not read tool permissions.",
      "vercel_not_approved",
      403
    );
  }

  const vercelPermission = permissionsResult.data.find(
    (p) => p.tool_id === "vercel"
  );
  const approvedStatuses = new Set(["approved", "connected_demo"]);
  if (!vercelPermission || !approvedStatuses.has(vercelPermission.status)) {
    return apiError(
      `Vercel permission must be approved or connected_demo before creating a project.`,
      "vercel_not_approved",
      403
    );
  }

  // Require existing GitHub repo
  const repoResult = await getLatestGitHubRepoForBusiness(businessId);
  if (repoResult.error || !repoResult.data) {
    return badRequest(
      "No GitHub repository found for this business. Create a repo first.",
      "github_repo_missing",
    );
  }
  const repo = repoResult.data;

  // Optionally prepare deployable scaffold
  if (prepareScaffold) {
    try {
      await prepareDeployableNextScaffold({
        businessId,
        userId: user.id,
        owner: repo.githubOwner,
        repo: repo.githubRepoName,
        businessName: business.idea_name,
        oneLineIdea: business.one_line_idea,
      });
    } catch (e) {
      return scaffoldErrorResponse(e);
    }
  }

  // Derive project name
  const rawName = requestedProjectName ?? business.idea_name;

  const projectName = sanitizeVercelProjectName(rawName);
  if (!projectName) {
    return badRequest(
      "Could not derive a valid Vercel project name from the business name.",
      "invalid_input",
    );
  }

  // Create Vercel project
  let projectResult;
  try {
    projectResult = await createVercelProjectWithSetup({
      businessId,
      projectName,
      gitRepoFullName: repo.githubRepoFullName,
      createDeployment,
    });
  } catch (e) {
    return apiError(
      e instanceof Error ? e.message : "Vercel project creation failed.",
      "vercel_create_failed",
      500
    );
  }

  // Log project creation
  await createAgentActivityLog({
    business_id: businessId,
    user_id: user.id,
    activity_type: "vercel_project_created",
    message: "Created Vercel project for this business.",
    metadata: {
      status: "created",
      assetType: "vercel_project",
      executionPhase: "deployment",
      vercelProjectId: projectResult.projectId,
      vercelProjectName: projectResult.projectName,
      vercelDashboardUrl: projectResult.dashboardUrl,
      vercelDeploymentUrl: projectResult.deploymentUrl ?? null,
      gitRepoFullName: projectResult.gitRepoFullName ?? repo.githubRepoFullName,
      productionBranch: projectResult.productionBranch ?? "main",
      warnings: projectResult.warnings,
    },
  });

  // Update Vercel tool permission to connected_demo
  try {
    await updateToolPermissionStatus({
      id: vercelPermission.id,
      action: "mark_connected_demo",
      userId: user.id,
    });
  } catch {
    // Non-fatal
  }

  capture("VERCEL_PROJECT_CREATED", user, { business_id: businessId });

  return Response.json({
    ok: true,
    data: {
      projectId: projectResult.projectId,
      projectName: projectResult.projectName,
      dashboardUrl: projectResult.dashboardUrl,
      ...(projectResult.deploymentUrl ? { deploymentUrl: projectResult.deploymentUrl } : {}),
      ...(projectResult.warnings.length > 0 ? { warnings: projectResult.warnings } : {}),
    },
  });
}
