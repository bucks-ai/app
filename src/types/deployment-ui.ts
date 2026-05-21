export type DeploymentStatus =
  | "not_deployed"
  | "no_project"
  | "queued"
  | "building"
  | "ready"
  | "live"
  | "failed"
  | "manual_action_required"
  | "unknown";

export type DeploymentProjectView = {
  projectId?: string | null;
  projectName?: string | null;
  dashboardUrl?: string | null;
  deploymentUrl?: string | null;
  gitRepoFullName?: string | null;
  productionBranch?: string | null;
  createdAt?: string | null;
};

export type DeploymentStatusView = {
  businessId?: string | null;
  status: DeploymentStatus;
  project: DeploymentProjectView | null;
  projectName?: string | null;
  liveUrl?: string | null;
  dashboardUrl?: string | null;
  latestCheckedAt?: string | null;
  latestDeploymentState?: string | null;
  warnings: string[];
  manualAction?: string | null;
};

export type DeploymentStatusResponse =
  | {
      ok: true;
      data: DeploymentStatusView;
      warning?: string;
    }
  | {
      ok: false;
      code: string;
      error: string;
      data?: DeploymentStatusView;
    };

export type RefreshDeploymentStatusResponse =
  | {
      ok: true;
      data: DeploymentStatusView;
      warning?: string;
    }
  | {
      ok: false;
      code: string;
      error: string;
      data?: DeploymentStatusView;
    };
