import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  getLatestBlueprintForBusinessMock,
  createMissionFromBlueprintMock,
  getLatestMissionForBusinessMock,
  limitMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  getLatestBlueprintForBusinessMock: vi.fn(),
  createMissionFromBlueprintMock: vi.fn(),
  getLatestMissionForBusinessMock: vi.fn(),
  limitMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("@/lib/rate-limit", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/rate-limit")>();
  return { ...actual, limit: limitMock };
});

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/projects", () => ({
  getBusinessById: getBusinessByIdMock,
  getLatestBlueprintForBusiness: getLatestBlueprintForBusinessMock,
}));

vi.mock("@/lib/missions", () => ({
  createMissionFromBlueprint: createMissionFromBlueprintMock,
  getLatestMissionForBusiness: getLatestMissionForBusinessMock,
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

const OWNED_BUSINESS = { id: "biz-1", user_id: "user-1", idea_name: "Acme" };

describe("POST /api/businesses/[id]/execute", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getLatestBlueprintForBusinessMock.mockReset();
    createMissionFromBlueprintMock.mockReset();
    getLatestMissionForBusinessMock.mockReset();
    limitMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    limitMock.mockResolvedValue({ allowed: true, remaining: 4 });
  });

  it("returns the standard 401 envelope and never compiles a mission when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(401);
    expect(limitMock).not.toHaveBeenCalled();
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(createMissionFromBlueprintMock).not.toHaveBeenCalled();
  });

  it("returns the standard 429 envelope when the rate limit is exceeded", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    limitMock.mockResolvedValue({ allowed: false, remaining: 0 });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(429);
    expect(limitMock).toHaveBeenCalledWith("user-1:execute-business", { limit: 5, windowMs: 60_000 });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(createMissionFromBlueprintMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope when the business id path param is empty", async () => {
    const response = await POST(new Request("http://localhost"), makeParams(""));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.ok).toBe(false);
    expect(payload.code).toBe("validation_error");
    expect(requireUserMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(404);
    const payload = await response.json();
    expect(payload.code).toBe("business_not_found");
    expect(createMissionFromBlueprintMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "someone-else" },
      error: null,
    });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(createMissionFromBlueprintMock).not.toHaveBeenCalled();
  });

  it("returns 404 blueprint_not_found when the business has no saved blueprint", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });
    getLatestBlueprintForBusinessMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(404);
    const payload = await response.json();
    expect(payload.code).toBe("blueprint_not_found");
    expect(createMissionFromBlueprintMock).not.toHaveBeenCalled();
  });

  it("creates a mission from the compiled blueprint when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });
    getLatestBlueprintForBusinessMock.mockResolvedValue({
      data: { blueprint: { businessSummary: "An idea" } },
      error: null,
    });
    const mission = { id: "mission-1", status: "queued", runner_target: "business" };
    const tasks = [{ id: "task-1", title: "Build MVP" }];
    createMissionFromBlueprintMock.mockResolvedValue({ data: { mission, tasks }, error: null });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true, data: { mission, tasks } });
    expect(createMissionFromBlueprintMock).toHaveBeenCalledWith({
      businessId: "biz-1",
      userId: "user-1",
      businessName: "Acme",
      blueprint: { businessSummary: "An idea" },
    });
  });

  it("returns 500 when mission creation fails", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });
    getLatestBlueprintForBusinessMock.mockResolvedValue({
      data: { blueprint: { businessSummary: "An idea" } },
      error: null,
    });
    createMissionFromBlueprintMock.mockResolvedValue({
      data: null,
      error: "insert failed",
      code: "mission_create_failed",
    });

    const response = await POST(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(500);
    const payload = await response.json();
    expect(payload.code).toBe("mission_create_failed");
  });
});

describe("GET /api/businesses/[id]/execute", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getLatestMissionForBusinessMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(401);
    expect(getLatestMissionForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({
      data: { id: "biz-1", user_id: "someone-else" },
      error: null,
    });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(getLatestMissionForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns null when the business has no missions yet", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });
    getLatestMissionForBusinessMock.mockResolvedValue({ data: null, error: null });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true, data: { mission: null } });
  });

  it("returns the latest mission status", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });
    const mission = { id: "mission-1", status: "running", runner_target: "business" };
    getLatestMissionForBusinessMock.mockResolvedValue({ data: mission, error: null });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true, data: { mission } });
  });
});
