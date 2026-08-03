import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  hasSupabaseEnvMock,
  getCurrentUserMock,
  getBusinessByIdMock,
  getResearchWorkspaceMock,
  generateResearchWorkspaceFromBlueprintMock,
  limitMock,
} = vi.hoisted(() => ({
  hasSupabaseEnvMock: vi.fn(),
  getCurrentUserMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  getResearchWorkspaceMock: vi.fn(),
  generateResearchWorkspaceFromBlueprintMock: vi.fn(),
  limitMock: vi.fn(),
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/projects", () => ({
  getCurrentUser: getCurrentUserMock,
  getBusinessById: getBusinessByIdMock,
}));

vi.mock("@/lib/research", () => ({
  getResearchWorkspace: getResearchWorkspaceMock,
  generateResearchWorkspaceFromBlueprint: generateResearchWorkspaceFromBlueprintMock,
}));

vi.mock("@/lib/rate-limit", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/rate-limit")>();
  return { ...actual, limit: limitMock };
});

import { POST } from "./route";

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

function makeRequest(body: unknown) {
  return new Request("http://localhost/api/businesses/biz-1/research", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("POST /api/businesses/[id]/research", () => {
  beforeEach(() => {
    hasSupabaseEnvMock.mockReset();
    getCurrentUserMock.mockReset();
    getBusinessByIdMock.mockReset();
    getResearchWorkspaceMock.mockReset();
    generateResearchWorkspaceFromBlueprintMock.mockReset();
    limitMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    limitMock.mockResolvedValue({ allowed: true, remaining: 4 });
  });

  it("returns the standard 401 envelope and never generates when unauthenticated", async () => {
    getCurrentUserMock.mockResolvedValue({ data: null, error: "Not authenticated." });

    const response = await POST(makeRequest({ action: "generate" }), makeParams("biz-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(limitMock).not.toHaveBeenCalled();
    expect(generateResearchWorkspaceFromBlueprintMock).not.toHaveBeenCalled();
  });

  it("returns the standard 429 envelope and never generates when the rate limit is exceeded", async () => {
    getCurrentUserMock.mockResolvedValue({ data: { id: "user-1", email: "a@example.com" }, error: null });
    limitMock.mockResolvedValue({ allowed: false, remaining: 0 });

    const response = await POST(makeRequest({ action: "generate" }), makeParams("biz-1"));

    expect(response.status).toBe(429);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Too many requests. Please try again later.",
      code: "rate_limited",
    });
    expect(limitMock).toHaveBeenCalledWith("user-1:research-generate", { limit: 5, windowMs: 60_000 });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(generateResearchWorkspaceFromBlueprintMock).not.toHaveBeenCalled();
  });

  it("generates the research workspace when authenticated, owning the business, and under the rate limit", async () => {
    getCurrentUserMock.mockResolvedValue({ data: { id: "user-1", email: "a@example.com" }, error: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    generateResearchWorkspaceFromBlueprintMock.mockResolvedValue({ data: { id: "workspace-1" }, error: null });

    const response = await POST(makeRequest({ action: "generate" }), makeParams("biz-1"));

    expect(response.status).toBe(201);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      data: { id: "workspace-1" },
    });
  });

  it("returns 403 when the business belongs to another user", async () => {
    getCurrentUserMock.mockResolvedValue({ data: { id: "user-1", email: "a@example.com" }, error: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await POST(makeRequest({ action: "generate" }), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(generateResearchWorkspaceFromBlueprintMock).not.toHaveBeenCalled();
  });
});
