import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  hasVercelEnvMock,
  listVercelDeploymentsMock,
  getLatestVercelProjectForBusinessMock,
  createAgentActivityLogMock,
  getAgentActivityLogsMock,
  captureMock,
} = vi.hoisted(() => ({
  hasVercelEnvMock: vi.fn(),
  listVercelDeploymentsMock: vi.fn(),
  getLatestVercelProjectForBusinessMock: vi.fn(),
  createAgentActivityLogMock: vi.fn(),
  getAgentActivityLogsMock: vi.fn(),
  captureMock: vi.fn(),
}));

vi.mock("@/lib/vercel/env", () => ({
  hasVercelEnv: hasVercelEnvMock,
}));

vi.mock("@/lib/vercel/client", () => ({
  listVercelDeployments: listVercelDeploymentsMock,
}));

vi.mock("@/lib/vercel/project-metadata", () => ({
  getLatestVercelProjectForBusiness: getLatestVercelProjectForBusinessMock,
}));

vi.mock("@/lib/projects", () => ({
  createAgentActivityLog: createAgentActivityLogMock,
  getAgentActivityLogs: getAgentActivityLogsMock,
}));

vi.mock("@/lib/analytics/server", () => ({
  capture: captureMock,
}));

import { refreshVercelDeploymentStatusForBusiness } from "./deployment-status";

const readyDeployment = {
  uid: "dpl-1",
  name: "acme",
  url: "acme.vercel.app",
  state: "READY",
  target: "production",
  createdAt: 1,
  readyAt: 2,
};

describe("refreshVercelDeploymentStatusForBusiness", () => {
  beforeEach(() => {
    hasVercelEnvMock.mockReset().mockReturnValue(true);
    listVercelDeploymentsMock.mockReset();
    getLatestVercelProjectForBusinessMock.mockReset().mockResolvedValue({
      data: { vercelProjectId: "proj-1", vercelProjectName: "acme" },
      error: null,
    });
    createAgentActivityLogMock.mockReset().mockResolvedValue({ data: { id: "log-1" }, error: null });
    getAgentActivityLogsMock.mockReset().mockResolvedValue({ data: [], error: null });
    captureMock.mockReset();
  });

  it("captures deploy_succeeded the first time a deployment reports READY", async () => {
    listVercelDeploymentsMock.mockResolvedValue([readyDeployment]);
    getAgentActivityLogsMock.mockResolvedValue({ data: [], error: null });

    const result = await refreshVercelDeploymentStatusForBusiness("biz-1", { id: "user-1" });

    expect(result.data?.status).toBe("ready");
    expect(captureMock).toHaveBeenCalledWith("DEPLOY_SUCCEEDED", { id: "user-1" }, { business_id: "biz-1" });
    expect(captureMock).toHaveBeenCalledTimes(1);
  });

  it("does not capture deploy_succeeded again on a subsequent READY refresh", async () => {
    listVercelDeploymentsMock.mockResolvedValue([readyDeployment]);
    getAgentActivityLogsMock.mockResolvedValue({
      data: [{ id: "log-0", activity_type: "vercel_deployment_ready" }],
      error: null,
    });

    await refreshVercelDeploymentStatusForBusiness("biz-1", { id: "user-1" });

    expect(captureMock).not.toHaveBeenCalled();
  });

  it("does not capture deploy_succeeded when the deployment is still building", async () => {
    listVercelDeploymentsMock.mockResolvedValue([
      { ...readyDeployment, state: "BUILDING" },
    ]);

    const result = await refreshVercelDeploymentStatusForBusiness("biz-1", { id: "user-1" });

    expect(result.data?.status).toBe("building");
    expect(captureMock).not.toHaveBeenCalled();
  });

  it("does not capture deploy_succeeded when VERCEL_TOKEN is missing", async () => {
    hasVercelEnvMock.mockReturnValue(false);
    getLatestVercelProjectForBusinessMock.mockResolvedValue({
      data: { vercelProjectId: "proj-1", vercelProjectName: "acme", vercelDeploymentUrl: null },
      error: null,
    });

    const result = await refreshVercelDeploymentStatusForBusiness("biz-1", { id: "user-1" });

    expect(result.data?.status).toBe("manual_action_required");
    expect(captureMock).not.toHaveBeenCalled();
  });
});
