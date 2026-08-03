import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  hasVercelEnvMock,
  getBusinessByIdMock,
  createAgentActivityLogMock,
  getToolPermissionsForBusinessMock,
  updateToolPermissionStatusMock,
  getLatestGitHubRepoForBusinessMock,
  prepareDeployableNextScaffoldMock,
  sanitizeVercelProjectNameMock,
  createVercelProjectWithSetupMock,
  captureMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  hasVercelEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  createAgentActivityLogMock: vi.fn(),
  getToolPermissionsForBusinessMock: vi.fn(),
  updateToolPermissionStatusMock: vi.fn(),
  getLatestGitHubRepoForBusinessMock: vi.fn(),
  prepareDeployableNextScaffoldMock: vi.fn(),
  sanitizeVercelProjectNameMock: vi.fn(),
  createVercelProjectWithSetupMock: vi.fn(),
  captureMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("@/lib/analytics/server", () => ({
  capture: captureMock,
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/vercel/env", () => ({
  hasVercelEnv: hasVercelEnvMock,
}));

vi.mock("@/lib/projects", () => ({
  getBusinessById: getBusinessByIdMock,
  createAgentActivityLog: createAgentActivityLogMock,
}));

vi.mock("@/lib/tool-permissions", () => ({
  getToolPermissionsForBusiness: getToolPermissionsForBusinessMock,
  updateToolPermissionStatus: updateToolPermissionStatusMock,
}));

vi.mock("@/lib/github/repo-metadata", () => ({
  getLatestGitHubRepoForBusiness: getLatestGitHubRepoForBusinessMock,
}));

vi.mock("@/lib/github/next-scaffold", () => ({
  prepareDeployableNextScaffold: prepareDeployableNextScaffoldMock,
  ScaffoldPreparationError: class ScaffoldPreparationError extends Error {},
}));

vi.mock("@/lib/vercel/client", () => ({
  sanitizeVercelProjectName: sanitizeVercelProjectNameMock,
  createVercelProjectWithSetup: createVercelProjectWithSetupMock,
}));

import { POST } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeRequest(body: unknown) {
  return new NextRequest("http://localhost/api/vercel/create-project", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("POST /api/vercel/create-project", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    hasVercelEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    createAgentActivityLogMock.mockReset();
    getToolPermissionsForBusinessMock.mockReset();
    updateToolPermissionStatusMock.mockReset();
    getLatestGitHubRepoForBusinessMock.mockReset();
    prepareDeployableNextScaffoldMock.mockReset();
    sanitizeVercelProjectNameMock.mockReset();
    createVercelProjectWithSetupMock.mockReset();
    captureMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    hasVercelEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never touches Vercel when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(createVercelProjectWithSetupMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(404);
    expect(createVercelProjectWithSetupMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "someone-else", idea_name: "Acme" },
      error: null,
    });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(403);
    expect(createVercelProjectWithSetupMock).not.toHaveBeenCalled();
  });

  it("creates the project when authenticated, owning the business, and permission approved", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "user-1", idea_name: "Acme", one_line_idea: "An idea" },
      error: null,
    });
    getToolPermissionsForBusinessMock.mockResolvedValue({
      data: [{ id: "perm-1", tool_id: "vercel", status: "approved" }],
      error: null,
    });
    getLatestGitHubRepoForBusinessMock.mockResolvedValue({
      data: { githubRepoFullName: "user/acme" },
      error: null,
    });
    sanitizeVercelProjectNameMock.mockReturnValue("acme");
    createVercelProjectWithSetupMock.mockResolvedValue({
      projectId: "proj-1",
      projectName: "acme",
      dashboardUrl: "https://vercel.com/user/acme",
      deploymentUrl: undefined,
      gitRepoFullName: "user/acme",
      productionBranch: "main",
      warnings: [],
    });
    createAgentActivityLogMock.mockResolvedValue({ data: { id: "log-1" }, error: null });
    updateToolPermissionStatusMock.mockResolvedValue({ data: {}, error: null });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(200);
    expect(createVercelProjectWithSetupMock).toHaveBeenCalled();
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      data: { projectId: "proj-1" },
    });
    expect(captureMock).toHaveBeenCalledWith("VERCEL_PROJECT_CREATED", { id: "user-1" }, {
      business_id: "biz-1",
    });
  });

  it("returns a 400 badRequest envelope when businessId is missing", async () => {
    const response = await POST(makeRequest({ projectName: "acme" }));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.ok).toBe(false);
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.businessId).toBeDefined();
    expect(requireUserMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope when prepareScaffold is not a boolean", async () => {
    const response = await POST(
      makeRequest({ businessId: "biz-1", prepareScaffold: "yes" }),
    );

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.prepareScaffold).toBeDefined();
  });

  it("returns a 400 badRequest envelope for a malformed JSON body", async () => {
    const request = new NextRequest("http://localhost/api/vercel/create-project", {
      method: "POST",
      body: "{not valid json",
      headers: { "Content-Type": "application/json" },
    });

    const response = await POST(request);

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("invalid_json");
  });
});
