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
