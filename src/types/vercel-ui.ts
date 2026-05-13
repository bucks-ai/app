export type VercelProjectResult = {
  projectId?: string;
  projectName: string;
  dashboardUrl: string;
  deploymentUrl?: string | null;
  repoFullName?: string | null;
};

export type DeploymentActivityLog = {
  activityType: string;
  message: string;
  metadata: Record<string, unknown>;
  createdAt: string;
};

export type PrepareScaffoldInput = {
  businessId: string;
};

export type VercelCreateProjectInput = {
  businessId: string;
  projectName: string;
  prepareScaffold: boolean;
  attemptInitialDeployment: boolean;
};

export type VercelCreateProjectState =
  | {
      status: "idle";
      result: null;
      error: null;
      warning: null;
      code?: undefined;
    }
  | {
      status: "loading";
      result: null;
      error: null;
      warning: null;
      code?: undefined;
    }
  | {
      status: "success";
      result: VercelProjectResult;
      error: null;
      warning: string | null;
      code?: undefined;
    }
  | {
      status: "error";
      result: null;
      error: string;
      warning: null;
      code?: string;
    };

export type VercelProjectStatusResponse =
  | {
      ok: true;
      data: VercelProjectResult | null;
      warning?: string;
    }
  | {
      ok: false;
      code: string;
      error: string;
    };

export type VercelCreateProjectResponse =
  | {
      ok: true;
      data: VercelProjectResult;
      warning?: string;
    }
  | {
      ok: false;
      code: string;
      error: string;
    };

export type PrepareScaffoldResponse =
  | {
      ok: true;
      data: {
        files: string[];
        repoFullName?: string | null;
      };
      warning?: string;
    }
  | {
      ok: false;
      code: string;
      error: string;
    };
