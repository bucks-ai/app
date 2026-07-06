import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  getAgentRunsForBusinessMock,
  getAgentRunSummaryForBusinessMock,
  createAgentRunMock,
  getAgentTemplateMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  getAgentRunsForBusinessMock: vi.fn(),
  getAgentRunSummaryForBusinessMock: vi.fn(),
  createAgentRunMock: vi.fn(),
  getAgentTemplateMock: vi.fn(),
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
  getAgentRunsForBusiness: getAgentRunsForBusinessMock,
  getAgentRunSummaryForBusiness: getAgentRunSummaryForBusinessMock,
  createAgentRun: createAgentRunMock,
}));

vi.mock("@/lib/agents/registry", () => ({
  getAgentTemplate: getAgentTemplateMock,
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
  return new Request("http://localhost/api/businesses/biz-1/agent-runs", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("GET /api/businesses/[id]/agent-runs", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getAgentRunsForBusinessMock.mockReset();
    getAgentRunSummaryForBusinessMock.mockReset();
    createAgentRunMock.mockReset();
    getAgentTemplateMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never queries the business or runs when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(getAgentRunsForBusinessMock).not.toHaveBeenCalled();
    expect(getAgentRunSummaryForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(404);
    expect(getAgentRunsForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(getAgentRunsForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns runs and summary when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    getAgentRunsForBusinessMock.mockResolvedValue({ data: [], error: null });
    getAgentRunSummaryForBusinessMock.mockResolvedValue({
      data: {
        businessId: "biz-1",
        totalRuns: 0,
        completedRuns: 0,
        failedRuns: 0,
        runningRuns: 0,
        blockedRuns: 0,
        waitingRuns: 0,
        lastRunAt: null,
        agentsCovered: [],
        generatedAt: "2026-07-06T00:00:00.000Z",
      },
      error: null,
    });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.ok).toBe(true);
    expect(body.data.runs).toEqual([]);
  });
});

describe("POST /api/businesses/[id]/agent-runs", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getAgentRunsForBusinessMock.mockReset();
    getAgentRunSummaryForBusinessMock.mockReset();
    createAgentRunMock.mockReset();
    getAgentTemplateMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never creates a run when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await POST(
      makePostRequest({ agentId: "agent-1", title: "Run" }),
      makeParams("biz-1"),
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(createAgentRunMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await POST(
      makePostRequest({ agentId: "agent-1", title: "Run" }),
      makeParams("biz-1"),
    );

    expect(response.status).toBe(403);
    expect(createAgentRunMock).not.toHaveBeenCalled();
  });

  it("creates a run when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    getAgentTemplateMock.mockReturnValue({ node: "node-1" });
    createAgentRunMock.mockResolvedValue({ data: { id: "run-1" }, error: null });

    const response = await POST(
      makePostRequest({ agentId: "agent-1", title: "Run" }),
      makeParams("biz-1"),
    );

    expect(response.status).toBe(201);
    expect(createAgentRunMock).toHaveBeenCalledWith(
      expect.objectContaining({ business_id: "biz-1", user_id: "user-1" }),
    );
  });
});
