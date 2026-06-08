// Server-side Vercel deploy status gate.
//
// A reusable decision primitive that answers a single question: is a business's
// Vercel deployment in a state that should permit deploy-dependent actions
// (e.g. starting customer validation against a live URL)?
//
// `decideDeploymentGate` is a pure function over an already-normalized status,
// so it can be reused/tested without any network calls. `evaluateDeploymentGate`
// performs the live lookup (stored metadata + Vercel API, with a log/metadata
// fallback when no token is configured).
//
// Never import from client components.

import { hasVercelEnv } from "@/lib/vercel/env";
import {
  getLatestVercelDeploymentForProject,
  normalizeVercelDeploymentStatus,
  extractDeploymentUrl,
} from "@/lib/vercel/deployment-status";
import { getLatestVercelProjectForBusiness } from "@/lib/vercel/project-metadata";
import { getAgentActivityLogs } from "@/lib/projects";
import type { AgentActivityLogRecord } from "@/types/database";
import type {
  DeploymentStatus,
  DeploymentGateCode,
  DeploymentGateResult,
} from "@/types/deployment";

interface GateDecision {
  passed: boolean;
  code: DeploymentGateCode;
  reason: string;
}

// Pure verdict over a normalized deployment status. `hasProject` distinguishes
// "no project at all" from "project exists but not deployed yet".
export function decideDeploymentGate(input: {
  hasProject: boolean;
  status: DeploymentStatus;
  deploymentUrl: string | null;
}): GateDecision {
  if (!input.hasProject) {
    return {
      passed: false,
      code: "no_vercel_project",
      reason:
        "No Vercel project has been created for this business yet. Create and deploy a project before continuing.",
    };
  }

  switch (input.status) {
    case "ready":
      if (input.deploymentUrl) {
        return {
          passed: true,
          code: "ready",
          reason: "A live deployment is ready.",
        };
      }
      // Ready state but no usable URL — treat as indeterminate rather than pass.
      return {
        passed: false,
        code: "status_unknown",
        reason:
          "The deployment reports ready, but no live URL could be resolved. Refresh deployment status and try again.",
      };
    case "queued":
    case "building":
      return {
        passed: false,
        code: "deployment_in_progress",
        reason: "A deployment is in progress. Wait for it to finish, then try again.",
      };
    case "failed":
      return {
        passed: false,
        code: "deployment_failed",
        reason:
          "The latest Vercel deployment failed. Review the build logs and push a fix to the linked branch.",
      };
    case "canceled":
      return {
        passed: false,
        code: "deployment_canceled",
        reason:
          "The latest Vercel deployment was canceled. Trigger a new deployment to continue.",
      };
    case "manual_action_required":
      return {
        passed: false,
        code: "manual_action_required",
        reason:
          "No deployments were found for the Vercel project. Push to the linked branch or connect Git in the Vercel dashboard.",
      };
    case "not_started":
      return {
        passed: false,
        code: "no_deployment_found",
        reason: "The Vercel project has not been deployed yet.",
      };
    case "unknown":
    default:
      return {
        passed: false,
        code: "status_unknown",
        reason:
          "The deployment status could not be determined. Refresh deployment status and try again.",
      };
  }
}

// Resolves the most recent live deployment URL from a `vercel_deployment_ready`
// activity log, used as a fallback when the Vercel API cannot be queried.
function readyDeploymentUrlFromLogs(
  logs: AgentActivityLogRecord[]
): string | null {
  const readyLog = logs.find((log) => log.activity_type === "vercel_deployment_ready");
  const url = readyLog?.metadata?.deploymentUrl;
  return typeof url === "string" && url ? url : null;
}

// Live evaluation of the deploy gate for a business. Read-only: it never writes
// activity logs, so it is safe to call from any route handler.
export async function evaluateDeploymentGate(
  businessId: string
): Promise<DeploymentGateResult> {
  const checkedAt = new Date().toISOString();

  const metaResult = await getLatestVercelProjectForBusiness(businessId);
  if (metaResult.error || !metaResult.data) {
    const decision = decideDeploymentGate({
      hasProject: false,
      status: "not_started",
      deploymentUrl: null,
    });
    return {
      passed: decision.passed,
      code: decision.code,
      status: "not_started",
      reason: decision.reason,
      deploymentUrl: null,
      projectId: null,
      checkedAt,
      warnings: [],
    };
  }

  const meta = metaResult.data;
  const warnings: string[] = meta.warnings ? [...meta.warnings] : [];

  // No token: fall back to stored metadata / activity logs. If a ready URL was
  // recorded earlier, the gate can still pass; otherwise it requires manual action.
  if (!hasVercelEnv()) {
    const logsResult = await getAgentActivityLogs(businessId);
    const loggedUrl = logsResult.data
      ? readyDeploymentUrlFromLogs(logsResult.data)
      : null;
    const deploymentUrl = meta.vercelDeploymentUrl ?? loggedUrl;
    const status: DeploymentStatus = deploymentUrl ? "ready" : "manual_action_required";

    warnings.push(
      "VERCEL_TOKEN is not configured — gate evaluated from stored metadata only."
    );

    const decision = decideDeploymentGate({
      hasProject: true,
      status,
      deploymentUrl,
    });

    return {
      passed: decision.passed,
      code: decision.code,
      status,
      reason: decision.reason,
      deploymentUrl: decision.passed ? deploymentUrl : null,
      projectId: meta.vercelProjectId,
      checkedAt,
      warnings,
    };
  }

  // Live lookup against the Vercel API.
  const { deployment, warnings: fetchWarnings } =
    await getLatestVercelDeploymentForProject({ projectId: meta.vercelProjectId });
  warnings.push(...fetchWarnings);

  let status: DeploymentStatus;
  let deploymentUrl: string | null = null;

  if (!deployment) {
    status = "manual_action_required";
  } else {
    status = normalizeVercelDeploymentStatus(deployment.state);
    if (status === "ready") {
      deploymentUrl = extractDeploymentUrl(deployment);
    }
  }

  const decision = decideDeploymentGate({
    hasProject: true,
    status,
    deploymentUrl,
  });

  return {
    passed: decision.passed,
    code: decision.code,
    status,
    reason: decision.reason,
    deploymentUrl: decision.passed ? deploymentUrl : null,
    projectId: meta.vercelProjectId,
    checkedAt,
    warnings,
  };
}
