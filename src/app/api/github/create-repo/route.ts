import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { hasGitHubEnv, getGitHubEnv } from "@/lib/github/env";
import { getBusinessById, createAgentActivityLog } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { getToolPermissionsForBusiness, updateToolPermissionStatus } from "@/lib/tool-permissions";
import {
  createGitHubRepository,
  createStarterRepositoryFiles,
} from "@/lib/github/client";
import { apiError, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import { createGitHubRepoBodySchema } from "@/lib/schemas/infra";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";
import { capture } from "@/lib/analytics/server";

// Converts an arbitrary string into a valid GitHub repo name:
// lowercase, alphanumeric + hyphens only, max 100 chars, no leading/trailing hyphens.
function sanitizeRepoName(raw: string): string {
  return raw
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}

// ---------------------------------------------------------------------------
// POST /api/github/create-repo
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return apiError(
      "Supabase is not configured.",
      "missing_supabase_env",
      503
    );
  }

  if (!hasGitHubEnv()) {
    return apiError(
      "GitHub token is not configured. Add GITHUB_PERSONAL_ACCESS_TOKEN to .env.local.",
      "missing_github_env",
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

  const parsed = createGitHubRepoBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const {
    businessId,
    repoName: requestedRepoName,
    visibility = "private",
    includeStarterFiles = true,
  } = parsed.data;

  // Auth
  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:github-create-repo`, RATE_LIMITS.mutationDefault);
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

  // GitHub permission gate
  const permissionsResult = await getToolPermissionsForBusiness(businessId);
  if (permissionsResult.error || !permissionsResult.data) {
    return apiError(
      "Could not read tool permissions.",
      "github_permission_missing",
      403
    );
  }

  const githubPermission = permissionsResult.data.find(
    (p) => p.tool_id === "github"
  );

  if (!githubPermission) {
    return apiError(
      "GitHub tool permission has not been set up for this business. Seed tool permissions first.",
      "github_permission_missing",
      403
    );
  }

  const approvedStatuses = new Set(["approved", "connected_demo"]);
  if (!approvedStatuses.has(githubPermission.status)) {
    return apiError(
      `GitHub permission status is "${githubPermission.status}". It must be approved or connected_demo before creating a repository.`,
      "github_not_approved",
      403
    );
  }

  // Determine repo name
  const rawName = requestedRepoName ?? business.idea_name;

  const repoName = sanitizeRepoName(rawName);
  if (!repoName) {
    return badRequest("Could not derive a valid repo name from the business name.", "invalid_input");
  }

  // Determine owner
  const { defaultOwner } = getGitHubEnv();
  const owner = defaultOwner || undefined; // undefined → GitHub uses the authenticated user

  // Create repository
  let repoResult;
  try {
    repoResult = await createGitHubRepository({
      name: repoName,
      description: business.one_line_idea ?? `${business.idea_name} — created by bucks.ai`,
      visibility,
      owner,
    });
  } catch (e) {
    return apiError(
      e instanceof Error ? e.message : "GitHub repo creation failed.",
      "github_create_failed",
      500
    );
  }

  // Log repo creation
  const logResult = await createAgentActivityLog({
    business_id: businessId,
    user_id: user.id,
    activity_type: "github_repo_created",
    message: "Created GitHub repository for this business.",
    metadata: {
      status: "created",
      assetType: "github_repo",
      executionPhase: "repository",
      githubRepoUrl: repoResult.repoUrl,
      githubRepoFullName: repoResult.fullName,
      githubRepoId: repoResult.repoId,
      githubCloneUrl: repoResult.cloneUrl,
      githubOwner: repoResult.owner,
      githubRepoName: repoResult.name,
      visibility,
    },
  });

  const activityLogId = logResult.data?.id ?? undefined;

  // Create starter files (non-fatal if it fails)
  let starterFilesWarning: string | undefined;
  if (includeStarterFiles) {
    try {
      await createStarterRepositoryFiles({
        owner: repoResult.owner,
        repo: repoResult.name,
        businessName: business.idea_name,
        oneLineIdea: business.one_line_idea,
      });
    } catch (e) {
      starterFilesWarning =
        e instanceof Error
          ? e.message
          : "Starter file creation failed; the repository was created successfully.";
    }
  }

  // Update GitHub tool permission to connected_demo
  try {
    await updateToolPermissionStatus({
      id: githubPermission.id,
      action: "mark_connected_demo",
      userId: user.id,
    });
  } catch {
    // Non-fatal — don't fail the response over a status update
  }

  const responseBody: Record<string, unknown> = {
    ok: true,
    data: {
      repoUrl: repoResult.repoUrl,
      fullName: repoResult.fullName,
      owner: repoResult.owner,
      name: repoResult.name,
      private: repoResult.private,
      ...(activityLogId ? { activityLogId } : {}),
    },
  };

  if (starterFilesWarning) {
    responseBody.warning = starterFilesWarning;
  }

  capture("REPO_CREATED", user.id, { business_id: businessId });

  return Response.json(responseBody, { status: 201 });
}
