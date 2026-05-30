import type { VercelProjectResult } from "@/types/vercel-ui";
import type {
  DeploymentProjectView,
  DeploymentStatus,
  DeploymentStatusResponse,
  DeploymentStatusView,
  RefreshDeploymentStatusResponse,
} from "@/types/deployment-ui";

const DEPLOYMENT_API_UNAVAILABLE =
  "Deployment status backend is not available yet. Merge backend branch first.";

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

function errorCode(status: number, payload: unknown, fallback: string) {
  if (isRecord(payload) && typeof payload.code === "string" && payload.code.trim()) {
    return payload.code;
  }

  if (status === 404 || status === 405) return "api_unavailable";
  return fallback;
}

function friendlyError(status: number, code: string, payload: unknown) {
  const rawError =
    isRecord(payload) && typeof payload.error === "string" && payload.error.trim()
      ? payload.error
      : null;

  if (code === "api_unavailable" || status === 404 || status === 405) {
    return DEPLOYMENT_API_UNAVAILABLE;
  }

  return rawError ?? "Deployment status could not be loaded.";
}

function unwrapData(payload: unknown) {
  return isRecord(payload) && isRecord(payload.data) ? payload.data : payload;
}

function normalizeProject(value: unknown): DeploymentProjectView | null {
  if (!isRecord(value)) return null;

  const projectName =
    asString(value.projectName) ??
    asString(value.project_name) ??
    asString(value.vercelProjectName) ??
    asString(value.name);
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
    asString(value.vercel_deployment_url) ??
    asString(value.liveUrl) ??
    asString(value.live_url);

  if (!projectName && !dashboardUrl && !deploymentUrl) return null;

  return {
    projectId:
      asString(value.projectId) ??
      asString(value.project_id) ??
      asString(value.vercelProjectId) ??
      asString(value.id),
    projectName,
    dashboardUrl,
    deploymentUrl,
    gitRepoFullName:
      asString(value.gitRepoFullName) ??
      asString(value.git_repo_full_name) ??
      asString(value.repoFullName) ??
      asString(value.repo_full_name),
    productionBranch:
      asString(value.productionBranch) ?? asString(value.production_branch),
    createdAt: asString(value.createdAt) ?? asString(value.created_at),
  };
}

function latestDeployment(data: Record<string, unknown>): Record<string, unknown> | null {
  const deployments = Array.isArray(data.deployments) ? data.deployments : [];
  const records = deployments.filter(isRecord);
  return records[0] ?? null;
}

function normalizeUrl(value: string | null) {
  if (!value) return null;
  if (value.startsWith("http://") || value.startsWith("https://")) return value;
  return `https://${value}`;
}

function normalizeStatus(value: unknown): DeploymentStatus {
  const raw = asString(value)?.toLowerCase();

  if (!raw) return "unknown";
  if (raw === "ready" || raw === "live" || raw === "success") return "live";
  if (raw === "building" || raw === "initializing" || raw === "in_progress") return "building";
  if (raw === "queued" || raw === "pending") return "queued";
  if (raw === "error" || raw === "failed" || raw === "canceled") return "failed";
  if (
    raw === "manual_action_required" ||
    raw === "manual-action-required" ||
    raw === "action_required"
  ) {
    return "manual_action_required";
  }
  if (raw === "not_deployed" || raw === "not-deployed") return "not_deployed";
  if (raw === "no_project" || raw === "no-project") return "no_project";

  return "unknown";
}

function deriveStatus(
  data: Record<string, unknown>,
  project: DeploymentProjectView | null,
  deployment: Record<string, unknown> | null
): DeploymentStatus {
  const explicitStatus =
    normalizeStatus(data.status) !== "unknown"
      ? normalizeStatus(data.status)
      : normalizeStatus(data.deploymentStatus);
  if (explicitStatus !== "unknown") return explicitStatus;

  const deploymentState = normalizeStatus(deployment?.state);
  if (deploymentState !== "unknown") return deploymentState;

  if (!project) return "no_project";
  if (project.deploymentUrl) return "live";
  return "not_deployed";
}

function normalizeWarnings(data: Record<string, unknown>, payload: unknown) {
  return [
    ...asStringArray(data.warnings),
    ...(asString(data.warning) ? [asString(data.warning) as string] : []),
    ...(isRecord(payload) && asString(payload.warning) ? [asString(payload.warning) as string] : []),
  ];
}

export function deploymentViewFromProject(
  businessId: string,
  project: VercelProjectResult | null | undefined
): DeploymentStatusView {
  const normalizedProject = normalizeProject(project ?? null);

  return {
    businessId,
    status: normalizedProject
      ? normalizedProject.deploymentUrl
        ? "live"
        : "not_deployed"
      : "no_project",
    project: normalizedProject,
    projectName: normalizedProject?.projectName ?? null,
    liveUrl: normalizedProject?.deploymentUrl ?? null,
    dashboardUrl: normalizedProject?.dashboardUrl ?? null,
    latestCheckedAt: null,
    latestDeploymentState: null,
    warnings: [],
    manualAction: null,
  };
}

function normalizeDeploymentView(
  businessId: string,
  payload: unknown
): DeploymentStatusView {
  const data = unwrapData(payload);

  if (isRecord(data) && isRecord(data.view)) {
    return normalizeDeploymentView(businessId, data.view);
  }

  if (!isRecord(data)) {
    return deploymentViewFromProject(businessId, null);
  }

  const project =
    normalizeProject(data.vercelProject) ??
    normalizeProject(data.project) ??
    normalizeProject(data.deploymentProject);
  const deployment = latestDeployment(data);
  const status = deriveStatus(data, project, deployment);
  const deploymentUrl =
    normalizeUrl(project?.deploymentUrl ?? null) ??
    normalizeUrl(asString(deployment?.url)) ??
    normalizeUrl(asString(data.liveUrl)) ??
    normalizeUrl(asString(data.live_url));

  return {
    businessId,
    status,
    project: project ? { ...project, deploymentUrl } : null,
    projectName: project?.projectName ?? null,
    liveUrl: deploymentUrl,
    dashboardUrl: project?.dashboardUrl ?? null,
    latestCheckedAt:
      asString(data.latestCheckedAt) ??
      asString(data.checkedAt) ??
      asString(data.updatedAt) ??
      new Date().toISOString(),
    latestDeploymentState:
      asString(deployment?.state) ??
      asString(data.latestDeploymentState) ??
      asString(data.deploymentState),
    warnings: normalizeWarnings(data, payload),
    manualAction:
      asString(data.manualAction) ??
      asString(data.manual_action) ??
      (status === "manual_action_required"
        ? "Connect Git or push to main in Vercel/GitHub"
        : null),
  };
}

export async function fetchDeploymentStatus(
  businessId: string
): Promise<DeploymentStatusResponse> {
  try {
    const response = await fetch(
      `/api/vercel/project-status?businessId=${encodeURIComponent(businessId)}`
    );
    const payload = await readJson(response);
    const code = errorCode(response.status, payload, "request_failed");

    if (!response.ok || (isRecord(payload) && payload.ok === false)) {
      return {
        ok: false,
        code,
        error: friendlyError(response.status, code, payload),
      };
    }

    return {
      ok: true,
      data: normalizeDeploymentView(businessId, payload),
      warning: isRecord(payload) ? asString(payload.warning) ?? undefined : undefined,
    };
  } catch {
    return {
      ok: false,
      code: "network_error",
      error: "Could not reach the deployment status route.",
    };
  }
}

export async function refreshDeploymentStatus(
  businessId: string
): Promise<RefreshDeploymentStatusResponse> {
  try {
    const response = await fetch("/api/vercel/refresh-deployment-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ businessId }),
    });
    const payload = await readJson(response);
    const code = errorCode(response.status, payload, "refresh_failed");

    if (!response.ok || (isRecord(payload) && payload.ok === false)) {
      return {
        ok: false,
        code,
        error: friendlyError(response.status, code, payload),
      };
    }

    return {
      ok: true,
      data: normalizeDeploymentView(businessId, payload),
      warning: isRecord(payload) ? asString(payload.warning) ?? undefined : undefined,
    };
  } catch {
    return {
      ok: false,
      code: "network_error",
      error: "Could not reach the deployment refresh route.",
    };
  }
}
