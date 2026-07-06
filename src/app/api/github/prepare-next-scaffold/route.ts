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
import { badRequest, zodIssuesToFields } from "@/lib/api-error";
import { prepareNextScaffoldBodySchema } from "@/lib/schemas/infra";

type ErrorDetail = {
  failedFile?: string;
  githubStatusCode?: number;
  githubMessage?: string;
};

function errorResponse(
  error: string,
  code: string,
  status: number,
  detail?: ErrorDetail
) {
  return Response.json(
    { ok: false, error, code, ...(detail ? { detail } : {}) },
    { status }
  );
}

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

  return errorResponse(
    "Starter scaffold could not be written to GitHub.",
    "scaffold_failed",
    500,
    detail
  );
}

// ---------------------------------------------------------------------------
// POST /api/github/prepare-next-scaffold
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

  // Business ownership
  const businessResult = await getBusinessById(businessId);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }
  const business = businessResult.data;
  if (business.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  // Require GitHub env
  if (!hasGitHubEnv()) {
    return errorResponse(
      "GitHub token is not configured. Add GITHUB_PERSONAL_ACCESS_TOKEN to .env.local.",
      "github_env_missing",
      503
    );
  }

  // GitHub permission gate
  const permissionsResult = await getToolPermissionsForBusiness(businessId);
  if (permissionsResult.error || !permissionsResult.data) {
    return errorResponse(
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
    return errorResponse(
      `GitHub permission must be approved or connected_demo before preparing a scaffold.`,
      "github_not_approved",
      403
    );
  }

  // Require existing GitHub repo
  const repoResult = await getLatestGitHubRepoForBusiness(businessId);
  if (repoResult.error || !repoResult.data) {
    return errorResponse(
      "No GitHub repository found for this business. Create a repo first.",
      "github_repo_missing",
      400
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
