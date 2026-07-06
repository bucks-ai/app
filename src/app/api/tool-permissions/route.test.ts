import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  getToolPermissionsForBusinessMock,
  seedToolPermissionsForBusinessMock,
  createToolPermissionActivityLogMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  getToolPermissionsForBusinessMock: vi.fn(),
  seedToolPermissionsForBusinessMock: vi.fn(),
  createToolPermissionActivityLogMock: vi.fn(),
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

vi.mock("@/lib/tool-permissions", () => ({
  getToolPermissionsForBusiness: getToolPermissionsForBusinessMock,
  seedToolPermissionsForBusiness: seedToolPermissionsForBusinessMock,
  createToolPermissionActivityLog: createToolPermissionActivityLogMock,
}));

import { GET, POST } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeGetRequest(businessId?: string) {
  const url = businessId
    ? `http://localhost/api/tool-permissions?businessId=${businessId}`
    : "http://localhost/api/tool-permissions";
  return new NextRequest(url);
}

function makePostRequest(body: unknown) {
  return new NextRequest("http://localhost/api/tool-permissions", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("GET /api/tool-permissions", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getToolPermissionsForBusinessMock.mockReset();
    seedToolPermissionsForBusinessMock.mockReset();
    createToolPermissionActivityLogMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never queries the business when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await GET(makeGetRequest("biz-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(getToolPermissionsForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await GET(makeGetRequest("biz-1"));

    expect(response.status).toBe(404);
    expect(getToolPermissionsForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "someone-else" },
      error: null,
    });

    const response = await GET(makeGetRequest("biz-1"));

    expect(response.status).toBe(403);
    expect(getToolPermissionsForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns permissions when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "user-1" },
      error: null,
    });
    getToolPermissionsForBusinessMock.mockResolvedValue({ data: [], error: null });

    const response = await GET(makeGetRequest("biz-1"));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      data: { permissions: [], canSeed: true },
    });
  });
});

describe("POST /api/tool-permissions", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getToolPermissionsForBusinessMock.mockReset();
    seedToolPermissionsForBusinessMock.mockReset();
    createToolPermissionActivityLogMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never seeds when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await POST(makePostRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(seedToolPermissionsForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "someone-else" },
      error: null,
    });

    const response = await POST(makePostRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(403);
    expect(seedToolPermissionsForBusinessMock).not.toHaveBeenCalled();
  });

  it("seeds permissions when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "user-1" },
      error: null,
    });
    seedToolPermissionsForBusinessMock.mockResolvedValue({
      data: { seeded: 2, skipped: 0 },
      error: null,
    });

    const response = await POST(makePostRequest({ businessId: "biz-1" }));

    expect(response.status).toBe(200);
    expect(seedToolPermissionsForBusinessMock).toHaveBeenCalledWith("biz-1", "user-1");
    await expect(response.json()).resolves.toEqual({
      ok: true,
      data: { seeded: 2, skipped: 0 },
    });
  });
});
