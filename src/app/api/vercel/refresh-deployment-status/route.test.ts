import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  hasVercelEnvMock,
  getBusinessByIdMock,
  getLatestVercelProjectForBusinessMock,
  refreshVercelDeploymentStatusForBusinessMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  hasVercelEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  getLatestVercelProjectForBusinessMock: vi.fn(),
  refreshVercelDeploymentStatusForBusinessMock: vi.fn(),
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
  refreshVercelDeploymentStatusForBusiness: refreshVercelDeploymentStatusForBusinessMock,
}));

import { POST } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeRequest(body: unknown) {
  return new NextRequest("http://localhost/api/vercel/refresh-deployment-status", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("POST /api/vercel/refresh-deployment-status", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    hasVercelEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getLatestVercelProjectForBusinessMock.mockReset();
    refreshVercelDeploymentStatusForBusinessMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    hasVercelEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never queries the business when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(refreshVercelDeploymentStatusForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(404);
    expect(refreshVercelDeploymentStatusForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "someone-else" },
      error: null,
    });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(403);
    expect(refreshVercelDeploymentStatusForBusinessMock).not.toHaveBeenCalled();
  });

  it("refreshes deployment status when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "user-1" },
      error: null,
    });
    getLatestVercelProjectForBusinessMock.mockResolvedValue({
      data: { vercelProjectId: "proj-1", vercelDeploymentUrl: null },
      error: null,
    });
    refreshVercelDeploymentStatusForBusinessMock.mockResolvedValue({
      data: { status: "ready", deploymentUrl: "https://acme.vercel.app" },
      error: null,
    });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(200);
    expect(refreshVercelDeploymentStatusForBusinessMock).toHaveBeenCalledWith("biz-1", "user-1");
    await expect(response.json()).resolves.toEqual({
      ok: true,
      data: { status: "ready", deploymentUrl: "https://acme.vercel.app" },
    });
  });
});
