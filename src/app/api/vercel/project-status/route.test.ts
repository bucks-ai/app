import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  hasVercelEnvMock,
  getBusinessByIdMock,
  getLatestVercelProjectForBusinessMock,
  getLatestVercelDeploymentForProjectMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  hasVercelEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  getLatestVercelProjectForBusinessMock: vi.fn(),
  getLatestVercelDeploymentForProjectMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/vercel/env", () => ({
  hasVercelEnv: hasVercelEnvMock,
}));

vi.mock("@/lib/projects", () => ({
  getBusinessById: getBusinessByIdMock,
}));

vi.mock("@/lib/vercel/project-metadata", () => ({
  getLatestVercelProjectForBusiness: getLatestVercelProjectForBusinessMock,
}));

vi.mock("@/lib/vercel/deployment-status", () => ({
  getLatestVercelDeploymentForProject: getLatestVercelDeploymentForProjectMock,
  normalizeVercelDeploymentStatus: (s: string) => s,
  normalizeVercelDeploymentEnvironment: (s: string) => s,
  extractDeploymentUrl: () => null,
}));

import { GET } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeRequest(businessId?: string) {
  const url = businessId
    ? `http://localhost/api/vercel/project-status?businessId=${businessId}`
    : "http://localhost/api/vercel/project-status";
  return new NextRequest(url);
}

describe("GET /api/vercel/project-status", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    hasVercelEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getLatestVercelProjectForBusinessMock.mockReset();
    getLatestVercelDeploymentForProjectMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    hasVercelEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never queries the business when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await GET(makeRequest("biz-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(getLatestVercelProjectForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await GET(makeRequest("biz-1"));

    expect(response.status).toBe(404);
    expect(getLatestVercelProjectForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "someone-else" },
      error: null,
    });

    const response = await GET(makeRequest("biz-1"));

    expect(response.status).toBe(403);
    expect(getLatestVercelProjectForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns project status when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "user-1" },
      error: null,
    });
    getLatestVercelProjectForBusinessMock.mockResolvedValue({
      data: {
        vercelProjectId: "proj-1",
        vercelProjectName: "acme",
        vercelDashboardUrl: "https://vercel.com/user/acme",
        vercelDeploymentUrl: null,
        gitRepoFullName: "user/acme",
        productionBranch: "main",
        createdAt: "2026-01-01T00:00:00Z",
        warnings: [],
      },
      error: null,
    });
    getLatestVercelDeploymentForProjectMock.mockResolvedValue({
      deployment: null,
      warnings: [],
    });

    const response = await GET(makeRequest("biz-1"));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      data: { project: { projectId: "proj-1" } },
    });
  });
});
