import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  getBusinessExecutionStatusMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  getBusinessExecutionStatusMock: vi.fn(),
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

vi.mock("@/lib/execution/status", () => ({
  getBusinessExecutionStatus: getBusinessExecutionStatusMock,
}));

import { GET } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

describe("GET /api/businesses/[id]/execution-status", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getBusinessExecutionStatusMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never queries the business or status when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(getBusinessExecutionStatusMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(404);
    expect(getBusinessExecutionStatusMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(getBusinessExecutionStatusMock).not.toHaveBeenCalled();
  });

  it("returns the execution status when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    getBusinessExecutionStatusMock.mockResolvedValue({ data: { phase: "idle" }, error: null });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true, data: { phase: "idle" } });
  });
});
