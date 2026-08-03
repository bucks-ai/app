import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  getValidationWorkspaceMock,
  seedValidationWorkspaceFromBlueprintMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  getValidationWorkspaceMock: vi.fn(),
  seedValidationWorkspaceFromBlueprintMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/projects", () => ({
  getBusinessById: getBusinessByIdMock,
}));

vi.mock("@/lib/validation", () => ({
  getValidationWorkspace: getValidationWorkspaceMock,
  seedValidationWorkspaceFromBlueprint: seedValidationWorkspaceFromBlueprintMock,
}));

import { GET, POST } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

function makePostRequest(body: unknown) {
  return new Request("http://localhost/api/businesses/biz-1/validation", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("GET /api/businesses/[id]/validation", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getValidationWorkspaceMock.mockReset();
    seedValidationWorkspaceFromBlueprintMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never queries the business when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(getValidationWorkspaceMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(404);
    expect(getValidationWorkspaceMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(getValidationWorkspaceMock).not.toHaveBeenCalled();
  });

  it("returns the workspace when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    getValidationWorkspaceMock.mockResolvedValue({ data: { personas: [] }, error: null });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true, data: { personas: [] } });
  });
});

describe("POST /api/businesses/[id]/validation", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getValidationWorkspaceMock.mockReset();
    seedValidationWorkspaceFromBlueprintMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never seeds when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await POST(makePostRequest({ action: "seed" }), makeParams("biz-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(seedValidationWorkspaceFromBlueprintMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await POST(makePostRequest({ action: "seed" }), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(seedValidationWorkspaceFromBlueprintMock).not.toHaveBeenCalled();
  });

  it("seeds the workspace when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    seedValidationWorkspaceFromBlueprintMock.mockResolvedValue({ data: { personas: [] }, error: null });

    const response = await POST(makePostRequest({ action: "seed" }), makeParams("biz-1"));

    expect(response.status).toBe(201);
    expect(seedValidationWorkspaceFromBlueprintMock).toHaveBeenCalledWith("biz-1");
  });
});
