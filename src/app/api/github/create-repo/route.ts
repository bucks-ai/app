import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { hasGitHubEnv, getGitHubEnv } from "@/lib/github/env";
import { getCurrentUser, getBusinessById, createAgentActivityLog } from "@/lib/projects";
import { getToolPermissionsForBusiness, updateToolPermissionStatus } from "@/lib/tool-permissions";
import {
  createGitHubRepository,
  createStarterRepositoryFiles,
} from "@/lib/github/client";
import type { GitHubRepoVisibility } from "@/types/github";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

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
    return errorResponse(
      "Supabase is not configured.",
      "missing_supabase_env",
      503
    );
  }

  if (!hasGitHubEnv()) {
    return errorResponse(
      "GitHub token is not configured. Add GITHUB_PERSONAL_ACCESS_TOKEN to .env.local.",
      "missing_github_env",
      503
    );
  }

  // Parse body
  let body: {
    businessId?: unknown;
    repoName?: unknown;
    visibility?: unknown;
    includeStarterFiles?: unknown;
  };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return errorResponse("Request body must be valid JSON.", "invalid_input", 400);
  }

  const businessId =
    typeof body.businessId === "string" && body.businessId ? body.businessId : null;
  if (!businessId) {
    return errorResponse("businessId is required.", "invalid_input", 400);
  }

  const rawVisibility = body.visibility;
  const visibility: GitHubRepoVisibility =
    rawVisibility === "public" ? "public" : "private";

  const includeStarterFiles = body.includeStarterFiles !== false; // default true

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

  // GitHub permission gate
  const permissionsResult = await getToolPermissionsForBusiness(businessId);
  if (permissionsResult.error || !permissionsResult.data) {
    return errorResponse(
      "Could not read tool permissions.",
      "github_permission_missing",
      403
    );
  }

  const githubPermission = permissionsResult.data.find(
    (p) => p.tool_id === "github"
  );

  if (!githubPermission) {
    return errorResponse(
      "GitHub tool permission has not been set up for this business. Seed tool permissions first.",
      "github_permission_missing",
      403
    );
  }

  const approvedStatuses = new Set(["approved", "connected_demo"]);
  if (!approvedStatuses.has(githubPermission.status)) {
    return errorResponse(
      `GitHub permission status is "${githubPermission.status}". It must be approved or connected_demo before creating a repository.`,
      "github_not_approved",
      403
    );
  }

  // Determine repo name
  const rawName =
    typeof body.repoName === "string" && body.repoName.trim()
      ? body.repoName.trim()
      : business.idea_name;

  const repoName = sanitizeRepoName(rawName);
  if (!repoName) {
    return errorResponse(
      "Could not derive a valid repo name from the business name.",
      "invalid_input",
      400
    );
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
    return errorResponse(
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

  const response: Record<string, unknown> = {
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
    response.warning = starterFilesWarning;
  }

  return Response.json(response, { status: 201 });
}
