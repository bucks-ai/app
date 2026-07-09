import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { hasGitHubEnv } from "@/lib/github/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { getToolPermissionsForBusiness } from "@/lib/tool-permissions";
import { getLatestGitHubRepoForBusiness } from "@/lib/github/repo-metadata";
import {
  prepareDeployableNextScaffold,
  ScaffoldPreparationError,
} from "@/lib/github/next-scaffold";
import { apiError, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import { prepareNextScaffoldBodySchema } from "@/lib/schemas/infra";
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
// POST /api/github/prepare-next-scaffold
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return apiError(
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

  const parsed = prepareNextScaffoldBodySchema.safeParse(json);
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

  const rateLimitResult = await limit(`${user.id}:github-prepare-scaffold`, RATE_LIMITS.mutationDefault);
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

  // Require GitHub env
  if (!hasGitHubEnv()) {
    return apiError(
      "GitHub token is not configured. Add GITHUB_PERSONAL_ACCESS_TOKEN to .env.local.",
      "github_env_missing",
      503
    );
  }

  // GitHub permission gate
  const permissionsResult = await getToolPermissionsForBusiness(businessId);
  if (permissionsResult.error || !permissionsResult.data) {
    return apiError(
      "Could not read tool permissions.",
      "github_not_approved",
      403
    );
  }

  const githubPermission = permissionsResult.data.find(
    (p) => p.tool_id === "github"
  );
  const approvedStatuses = new Set(["approved", "connected_demo"]);
  if (!githubPermission || !approvedStatuses.has(githubPermission.status)) {
    return apiError(
      `GitHub permission must be approved or connected_demo before preparing a scaffold.`,
      "github_not_approved",
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

  // Prepare scaffold
  let scaffoldResult;
  try {
    scaffoldResult = await prepareDeployableNextScaffold({
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

  capture("SCAFFOLD_PREPARED", user.id, { business_id: businessId });

  return Response.json({
    ok: true,
    data: {
      filesWritten: scaffoldResult.filesWritten,
      files: scaffoldResult.files,
      repoUrl: repo.githubRepoUrl,
      activityLogId: scaffoldResult.activityLogId,
    },
  });
}
