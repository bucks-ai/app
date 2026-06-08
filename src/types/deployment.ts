// Types for deployment status tracking across providers.
// Server-side only — never import from client components.

export type DeploymentProvider = "vercel";

export type DeploymentStatus =
  | "not_started"
  | "queued"
  | "building"
  | "ready"
  | "failed"
  | "canceled"
  | "unknown"
  | "manual_action_required";

export type DeploymentEnvironment = "production" | "preview" | "unknown";

export interface DeploymentStatusRecord {
  provider: DeploymentProvider;
  status: DeploymentStatus;
  deploymentUrl: string | null;
  deploymentId: string | null;
  projectId: string;
  projectName: string;
  environment: DeploymentEnvironment;
  createdAt: string | null;
  readyAt: string | null;
  checkedAt: string;
  warnings: string[];
}

export interface DeploymentStatusResponse {
  ok: boolean;
  data?: {
    project: {
      projectId: string;
      projectName: string;
      dashboardUrl: string;
      gitRepoFullName: string | null;
      productionBranch: string | null;
      createdAt: string;
    };
    latestDeployment: {
      status: DeploymentStatus;
      deploymentUrl: string | null;
      deploymentId: string | null;
      environment: DeploymentEnvironment;
      createdAt: string | null;
      readyAt: string | null;
    } | null;
    storedMetadata: {
      deploymentUrl: string | null;
    };
    warnings: string[];
  };
  error?: string;
  code?: string;
}

export interface RefreshDeploymentStatusResult {
  status: DeploymentStatus;
  deploymentUrl: string | null;
  deploymentId: string | null;
  environment: DeploymentEnvironment;
  warnings: string[];
}

// ---------------------------------------------------------------------------
// Deploy status gate
//
// A reusable decision primitive that answers: "Is this business's deployment
// in a state that should permit deploy-dependent actions (e.g. customer
// validation against a live URL)?" Unlike the refresh result, the gate is a
// pure pass/blocked verdict with a machine-readable reason code.
// ---------------------------------------------------------------------------

export type DeploymentGateCode =
  | "ready"
  | "no_vercel_project"
  | "no_deployment_found"
  | "deployment_in_progress"
  | "deployment_failed"
  | "deployment_canceled"
  | "manual_action_required"
  | "status_unknown";

export interface DeploymentGateResult {
  // True only when a live, ready deployment URL is available.
  passed: boolean;
  // Machine-readable reason for the verdict.
  code: DeploymentGateCode;
  // Normalized deployment status the verdict was derived from.
  status: DeploymentStatus;
  // Human-readable explanation, safe to surface to founders.
  reason: string;
  // The live deployment URL when the gate passes, otherwise null.
  deploymentUrl: string | null;
  // The Vercel project the gate evaluated, when one exists.
  projectId: string | null;
  // ISO timestamp of when the gate was evaluated.
  checkedAt: string;
  // Non-fatal notes (e.g. missing token, fetch failures).
  warnings: string[];
}
