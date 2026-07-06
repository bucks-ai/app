import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  hasGitHubEnvMock,
  getGitHubEnvMock,
  getBusinessByIdMock,
  createAgentActivityLogMock,
  getToolPermissionsForBusinessMock,
  updateToolPermissionStatusMock,
  createGitHubRepositoryMock,
  createStarterRepositoryFilesMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  hasGitHubEnvMock: vi.fn(),
  getGitHubEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  createAgentActivityLogMock: vi.fn(),
  getToolPermissionsForBusinessMock: vi.fn(),
  updateToolPermissionStatusMock: vi.fn(),
  createGitHubRepositoryMock: vi.fn(),
  createStarterRepositoryFilesMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/github/env", () => ({
  hasGitHubEnv: hasGitHubEnvMock,
  getGitHubEnv: getGitHubEnvMock,
}));

vi.mock("@/lib/projects", () => ({
  getBusinessById: getBusinessByIdMock,
  createAgentActivityLog: createAgentActivityLogMock,
}));

vi.mock("@/lib/tool-permissions", () => ({
  getToolPermissionsForBusiness: getToolPermissionsForBusinessMock,
  updateToolPermissionStatus: updateToolPermissionStatusMock,
}));

vi.mock("@/lib/github/client", () => ({
  createGitHubRepository: createGitHubRepositoryMock,
  createStarterRepositoryFiles: createStarterRepositoryFilesMock,
}));

import { POST } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeRequest(body: unknown) {
  return new NextRequest("http://localhost/api/github/create-repo", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("POST /api/github/create-repo", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    hasGitHubEnvMock.mockReset();
    getGitHubEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    createAgentActivityLogMock.mockReset();
    getToolPermissionsForBusinessMock.mockReset();
    updateToolPermissionStatusMock.mockReset();
    createGitHubRepositoryMock.mockReset();
    createStarterRepositoryFilesMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    hasGitHubEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never touches GitHub when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(createGitHubRepositoryMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(404);
    expect(createGitHubRepositoryMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "someone-else", idea_name: "Acme" },
      error: null,
    });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(403);
    expect(createGitHubRepositoryMock).not.toHaveBeenCalled();
  });

  it("creates the repo when authenticated, owning the business, and permission approved", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "user-1", idea_name: "Acme", one_line_idea: "An idea" },
      error: null,
    });
    getToolPermissionsForBusinessMock.mockResolvedValue({
      data: [{ id: "perm-1", tool_id: "github", status: "approved" }],
      error: null,
    });
    getGitHubEnvMock.mockReturnValue({ token: "tok", defaultOwner: undefined });
    createGitHubRepositoryMock.mockResolvedValue({
      repoUrl: "https://github.com/user/acme",
      fullName: "user/acme",
      repoId: 1,
      cloneUrl: "https://github.com/user/acme.git",
      owner: "user",
      name: "acme",
      private: true,
    });
    createAgentActivityLogMock.mockResolvedValue({ data: { id: "log-1" }, error: null });
    createStarterRepositoryFilesMock.mockResolvedValue(undefined);
    updateToolPermissionStatusMock.mockResolvedValue({ data: {}, error: null });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(201);
    expect(createGitHubRepositoryMock).toHaveBeenCalled();
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      data: { fullName: "user/acme" },
    });
  });

  it("returns a 400 badRequest envelope when businessId is missing", async () => {
    const response = await POST(makeRequest({ repoName: "my-repo" }));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.ok).toBe(false);
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.businessId).toBeDefined();
    expect(requireUserMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope when visibility is not a valid enum value", async () => {
    const response = await POST(
      makeRequest({ businessId: "biz-1", visibility: "hidden" }),
    );

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.visibility).toBeDefined();
  });

  it("returns a 400 badRequest envelope for a malformed JSON body", async () => {
    const request = new NextRequest("http://localhost/api/github/create-repo", {
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
