// Server-side Vercel deployment status helpers.
// Never import from client components.

import { hasVercelEnv } from "@/lib/vercel/env";
import { listVercelDeployments } from "@/lib/vercel/client";
import { getLatestVercelProjectForBusiness } from "@/lib/vercel/project-metadata";
import { createAgentActivityLog } from "@/lib/projects";
import type { VercelDeploymentRecord } from "@/types/vercel";
import type {
  DeploymentStatus,
  DeploymentEnvironment,
  RefreshDeploymentStatusResult,
} from "@/types/deployment";

type Result<T> =
  | { data: T; error: null }
  | { data: null; error: string };

export function normalizeVercelDeploymentStatus(rawStatus: string): DeploymentStatus {
  switch (rawStatus.toUpperCase()) {
    case "QUEUED":
      return "queued";
    case "INITIALIZING":
    case "BUILDING":
      return "building";
    case "READY":
      return "ready";
    case "ERROR":
      return "failed";
    case "CANCELED":
      return "canceled";
    default:
      return "unknown";
  }
}

export function normalizeVercelDeploymentEnvironment(
  target?: string | null
): DeploymentEnvironment {
  if (target === "production") return "production";
  if (target === "staging" || target === "preview") return "preview";
  return "unknown";
}

export function extractDeploymentUrl(
  deployment: VercelDeploymentRecord
): string | null {
  if (!deployment.url) return null;
  const raw = deployment.url;
  return raw.startsWith("http") ? raw : `https://${raw}`;
}

export async function getLatestVercelDeploymentForProject(input: {
  projectId: string;
}): Promise<{ deployment: VercelDeploymentRecord | null; warnings: string[] }> {
  const warnings: string[] = [];

  if (!hasVercelEnv()) {
    return {
      deployment: null,
      warnings: ["VERCEL_TOKEN is not set — cannot fetch live deployments."],
    };
  }

  try {
    const deployments = await listVercelDeployments({
      projectId: input.projectId,
      limit: 5,
    });

    if (deployments.length === 0) {
      return { deployment: null, warnings };
    }

    // listVercelDeployments returns newest-first from the API
    return { deployment: deployments[0], warnings };
  } catch (e) {
    warnings.push(
      `Could not fetch deployments: ${e instanceof Error ? e.message : String(e)}`
    );
    return { deployment: null, warnings };
  }
}

export async function refreshVercelDeploymentStatusForBusiness(
  businessId: string,
  userId: string
): Promise<Result<RefreshDeploymentStatusResult>> {
  // Load stored Vercel project metadata
  const metaResult = await getLatestVercelProjectForBusiness(businessId);
  if (metaResult.error || !metaResult.data) {
    return { data: null, error: "No Vercel project found for this business." };
  }

  const meta = metaResult.data;
  const warnings: string[] = meta.warnings ? [...meta.warnings] : [];
  const checkedAt = new Date().toISOString();

  // If no Vercel token, return manual_action_required with stored info
  if (!hasVercelEnv()) {
    warnings.push("VERCEL_TOKEN is not set — showing stored metadata only.");

    await createAgentActivityLog({
      business_id: businessId,
      user_id: userId,
      activity_type: "vercel_deployment_status_refreshed",
      message: "Refreshed Vercel deployment status.",
      metadata: {
        provider: "vercel",
        status: "manual_action_required",
        deploymentUrl: meta.vercelDeploymentUrl ?? null,
        deploymentId: null,
        projectId: meta.vercelProjectId,
        projectName: meta.vercelProjectName,
        environment: "unknown",
        checkedAt,
        warnings,
      },
    });

    return {
      data: {
        status: "manual_action_required",
        deploymentUrl: meta.vercelDeploymentUrl ?? null,
        deploymentId: null,
        environment: "unknown",
        warnings,
      },
      error: null,
    };
  }

  // Fetch latest deployment from Vercel
  const { deployment, warnings: fetchWarnings } =
    await getLatestVercelDeploymentForProject({
      projectId: meta.vercelProjectId,
    });

  warnings.push(...fetchWarnings);

  let status: DeploymentStatus;
  let deploymentUrl: string | null = null;
  let deploymentId: string | null = null;
  let environment: DeploymentEnvironment = "unknown";
  let createdAt: string | null = null;
  let readyAt: string | null = null;

  if (!deployment) {
    // No deployments found — project exists but nothing has been deployed yet.
    // Most likely the GitHub integration is not fully set up.
    status = "manual_action_required";
    warnings.push(
      "No deployments found. You may need to push to the linked branch or connect Git manually in the Vercel dashboard."
    );
  } else {
    status = normalizeVercelDeploymentStatus(deployment.state);
    environment = normalizeVercelDeploymentEnvironment(deployment.target);
    deploymentId = deployment.uid;

    if (deployment.createdAt) {
      createdAt = new Date(deployment.createdAt).toISOString();
    }
    if (deployment.readyAt) {
      readyAt = new Date(deployment.readyAt).toISOString();
    }

    if (status === "ready") {
      deploymentUrl = extractDeploymentUrl(deployment);
    }
  }

  const sharedMeta = {
    provider: "vercel",
    status,
    deploymentUrl,
    deploymentId,
    projectId: meta.vercelProjectId,
    projectName: meta.vercelProjectName,
    environment,
    checkedAt,
    warnings: warnings.length > 0 ? warnings : undefined,
  };

  // Always log the status refresh
  await createAgentActivityLog({
    business_id: businessId,
    user_id: userId,
    activity_type: "vercel_deployment_status_refreshed",
    message: "Refreshed Vercel deployment status.",
    metadata: sharedMeta,
  });

  // Log ready event
  if (status === "ready" && deploymentUrl) {
    await createAgentActivityLog({
      business_id: businessId,
      user_id: userId,
      activity_type: "vercel_deployment_ready",
      message: "Vercel deployment is live.",
      metadata: {
        ...sharedMeta,
        deploymentUrl,
        readyAt,
      },
    });
  }

  // Log failed event
  if (status === "failed") {
    await createAgentActivityLog({
      business_id: businessId,
      user_id: userId,
      activity_type: "vercel_deployment_failed",
      message: "Vercel deployment failed.",
      metadata: {
        ...sharedMeta,
        deploymentId,
        createdAt,
      },
    });
  }

  return {
    data: {
      status,
      deploymentUrl,
      deploymentId,
      environment,
      warnings,
    },
    error: null,
  };
}
