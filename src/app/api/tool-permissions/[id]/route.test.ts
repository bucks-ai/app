import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getToolPermissionByIdMock,
  updateToolPermissionStatusMock,
  createToolPermissionActivityLogMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getToolPermissionByIdMock: vi.fn(),
  updateToolPermissionStatusMock: vi.fn(),
  createToolPermissionActivityLogMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/tool-permissions", () => ({
  getToolPermissionById: getToolPermissionByIdMock,
  updateToolPermissionStatus: updateToolPermissionStatusMock,
  createToolPermissionActivityLog: createToolPermissionActivityLogMock,
}));

import { PATCH } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

function makeRequest(body: unknown) {
  return new NextRequest("http://localhost/api/tool-permissions/perm-1", {
    method: "PATCH",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("PATCH /api/tool-permissions/[id]", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getToolPermissionByIdMock.mockReset();
    updateToolPermissionStatusMock.mockReset();
    createToolPermissionActivityLogMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    createToolPermissionActivityLogMock.mockResolvedValue({ data: {}, error: null });
  });

  it("returns the standard 401 envelope and never fetches the permission when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await PATCH(makeRequest({ action: "approve" }), makeParams("perm-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getToolPermissionByIdMock).not.toHaveBeenCalled();
    expect(updateToolPermissionStatusMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the permission does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getToolPermissionByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await PATCH(makeRequest({ action: "approve" }), makeParams("perm-1"));

    expect(response.status).toBe(404);
    expect(updateToolPermissionStatusMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the permission belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getToolPermissionByIdMock.mockResolvedValue({
      data: { id: "perm-1", user_id: "someone-else", tool_id: "github", tool_name: "GitHub" },
      error: null,
    });

    const response = await PATCH(makeRequest({ action: "approve" }), makeParams("perm-1"));

    expect(response.status).toBe(403);
    expect(updateToolPermissionStatusMock).not.toHaveBeenCalled();
  });

  it("updates the permission when authenticated and owning the record", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getToolPermissionByIdMock.mockResolvedValue({
      data: {
        id: "perm-1",
        user_id: "user-1",
        business_id: "biz-1",
        tool_id: "github",
        tool_name: "GitHub",
        status: "pending",
      },
      error: null,
    });
    updateToolPermissionStatusMock.mockResolvedValue({
      data: { id: "perm-1", status: "approved" },
      error: null,
    });

    const response = await PATCH(makeRequest({ action: "approve" }), makeParams("perm-1"));

    expect(response.status).toBe(200);
    expect(updateToolPermissionStatusMock).toHaveBeenCalledWith({
      id: "perm-1",
      action: "approve",
      userId: "user-1",
    });
    await expect(response.json()).resolves.toEqual({
      ok: true,
      data: { id: "perm-1", status: "approved" },
    });
  });

  it("returns a 400 badRequest envelope when action is missing", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });

    const response = await PATCH(makeRequest({}), makeParams("perm-1"));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.ok).toBe(false);
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.action).toBeDefined();
    expect(getToolPermissionByIdMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope when action is not a valid enum value", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });

    const response = await PATCH(
      makeRequest({ action: "delete_everything" }),
      makeParams("perm-1"),
    );

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.action).toBeDefined();
    expect(getToolPermissionByIdMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope for a malformed JSON body", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });

    const request = new NextRequest("http://localhost/api/tool-permissions/perm-1", {
      method: "PATCH",
      body: "{not valid json",
      headers: { "Content-Type": "application/json" },
    });

    const response = await PATCH(request, makeParams("perm-1"));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("invalid_json");
  });
});
