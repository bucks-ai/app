import type {
  PrepareScaffoldInput,
  PrepareScaffoldResponse,
  VercelCreateProjectInput,
  VercelCreateProjectResponse,
  VercelProjectResult,
  VercelProjectStatusResponse,
} from "@/types/vercel-ui";

const VERCEL_API_UNAVAILABLE =
  "Vercel backend route is not available yet. Merge backend branch first.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter(
        (item): item is string => typeof item === "string" && item.trim().length > 0
      )
    : [];
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function normalizeErrorCode(status: number, payload: unknown, fallback: string) {
  if (isRecord(payload) && typeof payload.code === "string" && payload.code.trim()) {
    return payload.code;
  }

  if (status === 404 || status === 405) return "api_unavailable";
  if (status === 401 || status === 403) return "vercel_not_approved";
  return fallback;
}

function friendlyError(status: number, code: string, payload: unknown) {
  const rawError =
    isRecord(payload) && typeof payload.error === "string" && payload.error.trim()
      ? payload.error
      : null;

  if (code === "api_unavailable" || status === 404 || status === 405) {
    return VERCEL_API_UNAVAILABLE;
  }

  if (
    code === "missing_vercel_env" ||
    code === "vercel_token_missing" ||
    code === "token_missing" ||
    code.toLowerCase().includes("token") ||
    rawError?.toLowerCase().includes("token")
  ) {
    return "Vercel token is not configured on the server.";
  }

  if (code === "github_repo_missing" || rawError?.toLowerCase().includes("github repo")) {
    return "Create a GitHub repo first.";
  }

  if (
    code === "vercel_not_approved" ||
    code === "vercel_permission_missing" ||
    code === "permission_required" ||
    code === "permission_missing" ||
    status === 401 ||
    status === 403
  ) {
    return "Approve Vercel in Tool Setup Queue first.";
  }

  if (code === "scaffold_failed") {
    return "Starter scaffold could not be written to GitHub. This can happen if the repo token lacks Contents: Read/Write permission or an existing file update failed.";
  }

  if (code === "vercel_create_failed") {
    return "Vercel could not create the project. Check token/team/GitHub integration access.";
  }

  return rawError ?? "Vercel could not complete the request.";
}

function normalizeProjectResult(value: unknown): VercelProjectResult | null {
  if (!isRecord(value)) return null;

  const projectName =
    asString(value.projectName) ?? asString(value.project_name) ?? asString(value.name);
  const dashboardUrl =
    asString(value.dashboardUrl) ??
    asString(value.dashboard_url) ??
    asString(value.vercelDashboardUrl) ??
    asString(value.vercel_dashboard_url) ??
    asString(value.url);
  const deploymentUrl =
    asString(value.deploymentUrl) ??
    asString(value.deployment_url) ??
    asString(value.vercelDeploymentUrl) ??
    asString(value.vercel_deployment_url);

  if (!projectName || !dashboardUrl) return null;

  return {
    projectId:
      asString(value.projectId) ??
      asString(value.project_id) ??
      asString(value.vercelProjectId) ??
      asString(value.id) ??
      undefined,
    projectName,
    dashboardUrl,
    deploymentUrl,
    repoFullName:
      asString(value.repoFullName) ??
      asString(value.repo_full_name) ??
      asString(value.githubRepoFullName) ??
      asString(value.github_repo_full_name),
  };
}

function unwrapData(payload: unknown) {
  return isRecord(payload) && isRecord(payload.data) ? payload.data : payload;
}

export async function prepareNextScaffold(
  input: PrepareScaffoldInput
): Promise<PrepareScaffoldResponse> {
  try {
    const response = await fetch("/api/github/prepare-next-scaffold", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    const payload = await readJson(response);
    const code = normalizeErrorCode(response.status, payload, "scaffold_failed");

    if (!response.ok || (isRecord(payload) && payload.ok === false)) {
      return { ok: false, code, error: friendlyError(response.status, code, payload) };
    }

    const data = unwrapData(payload);
    const files = isRecord(data)
      ? asStringArray(data.files).length > 0
        ? asStringArray(data.files)
        : asStringArray(data.filesWritten).length > 0
          ? asStringArray(data.filesWritten)
        : asStringArray(data.writtenFiles)
      : [];

    return {
      ok: true,
      data: {
        files,
        repoFullName: isRecord(data)
          ? asString(data.repoFullName) ?? asString(data.githubRepoFullName)
          : null,
      },
      warning: isRecord(payload) ? asString(payload.warning) ?? undefined : undefined,
    };
  } catch {
    return { ok: false, code: "network_error", error: "Could not reach the scaffold route." };
  }
}

export async function createVercelProject(
  input: VercelCreateProjectInput
): Promise<VercelCreateProjectResponse> {
  try {
    const response = await fetch("/api/vercel/create-project", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    const payload = await readJson(response);
    const code = normalizeErrorCode(response.status, payload, "vercel_create_failed");

    if (!response.ok || (isRecord(payload) && payload.ok === false)) {
      return { ok: false, code, error: friendlyError(response.status, code, payload) };
    }

    const data = normalizeProjectResult(unwrapData(payload));
    if (!data) {
      return {
        ok: false,
        code: "invalid_response",
        error: "Vercel backend returned project data in an unexpected shape.",
      };
    }

    return {
      ok: true,
      data,
      warning: isRecord(payload) ? asString(payload.warning) ?? undefined : undefined,
    };
  } catch {
    return { ok: false, code: "network_error", error: "Could not reach the Vercel project route." };
  }
}

export async function fetchVercelProjectStatus(
  businessId: string
): Promise<VercelProjectStatusResponse> {
  try {
    const response = await fetch(
      `/api/vercel/project-status?businessId=${encodeURIComponent(businessId)}`
    );
    const payload = await readJson(response);
    const code = normalizeErrorCode(response.status, payload, "request_failed");

    if (!response.ok || (isRecord(payload) && payload.ok === false)) {
      return { ok: false, code, error: friendlyError(response.status, code, payload) };
    }

    const data = normalizeProjectResult(unwrapData(payload));
    return {
      ok: true,
      data,
      warning: isRecord(payload) ? asString(payload.warning) ?? undefined : undefined,
    };
  } catch {
    return { ok: false, code: "network_error", error: "Could not reach the Vercel status route." };
  }
}
