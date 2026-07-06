import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  inferAgentRunsFromActivityLogsMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  inferAgentRunsFromActivityLogsMock: vi.fn(),
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

vi.mock("@/lib/agents/runs", () => ({
  inferAgentRunsFromActivityLogs: inferAgentRunsFromActivityLogsMock,
}));

import { POST } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

describe("POST /api/businesses/[id]/agent-runs/infer", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    inferAgentRunsFromActivityLogsMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never runs inference when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(inferAgentRunsFromActivityLogsMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(404);
    expect(inferAgentRunsFromActivityLogsMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(inferAgentRunsFromActivityLogsMock).not.toHaveBeenCalled();
  });

  it("runs inference when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    inferAgentRunsFromActivityLogsMock.mockResolvedValue({ data: { created: 2, skipped: 1 }, error: null });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      data: { created: 2, skipped: 1 },
    });
  });

  it("returns a 400 badRequest envelope when the business id path param is empty", async () => {
    const response = await POST(new Request("http://localhost"), makeParams(""));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.ok).toBe(false);
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.id).toBeDefined();
    expect(requireUserMock).not.toHaveBeenCalled();
    expect(inferAgentRunsFromActivityLogsMock).not.toHaveBeenCalled();
  });
});
