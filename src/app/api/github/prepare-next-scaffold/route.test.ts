import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  hasGitHubEnvMock,
  getBusinessByIdMock,
  getToolPermissionsForBusinessMock,
  getLatestGitHubRepoForBusinessMock,
  prepareDeployableNextScaffoldMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  hasGitHubEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  getToolPermissionsForBusinessMock: vi.fn(),
  getLatestGitHubRepoForBusinessMock: vi.fn(),
  prepareDeployableNextScaffoldMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/github/env", () => ({
  hasGitHubEnv: hasGitHubEnvMock,
}));

vi.mock("@/lib/projects", () => ({
  getBusinessById: getBusinessByIdMock,
}));

vi.mock("@/lib/tool-permissions", () => ({
  getToolPermissionsForBusiness: getToolPermissionsForBusinessMock,
}));

vi.mock("@/lib/github/repo-metadata", () => ({
  getLatestGitHubRepoForBusiness: getLatestGitHubRepoForBusinessMock,
}));

vi.mock("@/lib/github/next-scaffold", () => ({
  prepareDeployableNextScaffold: prepareDeployableNextScaffoldMock,
  ScaffoldPreparationError: class ScaffoldPreparationError extends Error {},
}));

import { POST } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeRequest(body: unknown) {
  return new NextRequest("http://localhost/api/github/prepare-next-scaffold", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("POST /api/github/prepare-next-scaffold", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    hasGitHubEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getToolPermissionsForBusinessMock.mockReset();
    getLatestGitHubRepoForBusinessMock.mockReset();
    prepareDeployableNextScaffoldMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    hasGitHubEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never touches the business when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(prepareDeployableNextScaffoldMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(404);
    expect(prepareDeployableNextScaffoldMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "someone-else", idea_name: "Acme" },
      error: null,
    });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(403);
    expect(prepareDeployableNextScaffoldMock).not.toHaveBeenCalled();
  });

  it("prepares the scaffold when authenticated, owning the business, and permission approved", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "user-1", idea_name: "Acme", one_line_idea: "An idea" },
      error: null,
    });
    getToolPermissionsForBusinessMock.mockResolvedValue({
      data: [{ id: "perm-1", tool_id: "github", status: "approved" }],
      error: null,
    });
    getLatestGitHubRepoForBusinessMock.mockResolvedValue({
      data: {
        githubOwner: "user",
        githubRepoName: "acme",
        githubRepoUrl: "https://github.com/user/acme",
      },
      error: null,
    });
    prepareDeployableNextScaffoldMock.mockResolvedValue({
      filesWritten: 3,
      files: ["a", "b", "c"],
      activityLogId: "log-1",
    });

    const response = await POST(makeRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(200);
    expect(prepareDeployableNextScaffoldMock).toHaveBeenCalled();
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      data: { filesWritten: 3 },
    });
  });
});
