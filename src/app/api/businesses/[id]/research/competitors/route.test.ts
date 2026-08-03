import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  getCurrentUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  createResearchCompetitorMock,
  updateResearchCompetitorMock,
} = vi.hoisted(() => ({
  getCurrentUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  createResearchCompetitorMock: vi.fn(),
  updateResearchCompetitorMock: vi.fn(),
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/projects", () => ({
  getCurrentUser: getCurrentUserMock,
  getBusinessById: getBusinessByIdMock,
}));

vi.mock("@/lib/research", () => ({
  createResearchCompetitor: createResearchCompetitorMock,
  updateResearchCompetitor: updateResearchCompetitorMock,
}));

import { POST, PATCH } from "./route";

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

function makeRequest(method: string, body: unknown) {
  return new Request("http://localhost/api/businesses/biz-1/research/competitors", {
    method,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("POST /api/businesses/[id]/research/competitors", () => {
  beforeEach(() => {
    getCurrentUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    createResearchCompetitorMock.mockReset();
    updateResearchCompetitorMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  const validBody = { name: "Acme Corp" };

  it("returns 401 and never creates when unauthenticated", async () => {
    getCurrentUserMock.mockResolvedValue({ data: null, error: "unauthenticated" });

    const response = await POST(makeRequest("POST", validBody), makeParams("biz-1"));

    expect(response.status).toBe(401);
    expect(createResearchCompetitorMock).not.toHaveBeenCalled();
  });

  it("creates the competitor scoped to the authenticated user when authorized", async () => {
    getCurrentUserMock.mockResolvedValue({ data: { id: "user-1" }, error: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    createResearchCompetitorMock.mockResolvedValue({ data: { id: "comp-1" }, error: null });

    const response = await POST(makeRequest("POST", validBody), makeParams("biz-1"));

    expect(response.status).toBe(201);
    expect(createResearchCompetitorMock).toHaveBeenCalledWith(
      expect.objectContaining({ business_id: "biz-1", user_id: "user-1", name: validBody.name }),
    );
  });

  it("returns a 400 validation_error envelope and never creates when name is missing", async () => {
    getCurrentUserMock.mockResolvedValue({ data: { id: "user-1" }, error: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });

    const response = await POST(makeRequest("POST", {}), makeParams("biz-1"));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.ok).toBe(false);
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.name).toBeDefined();
    expect(createResearchCompetitorMock).not.toHaveBeenCalled();
  });

  it("returns a 400 validation_error envelope and never creates when category is not a known enum value", async () => {
    getCurrentUserMock.mockResolvedValue({ data: { id: "user-1" }, error: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });

    const response = await POST(
      makeRequest("POST", { name: "Acme Corp", category: "not-a-real-category" }),
      makeParams("biz-1"),
    );

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.category).toBeDefined();
    expect(createResearchCompetitorMock).not.toHaveBeenCalled();
  });

  it("returns a 400 invalid_json envelope for a malformed JSON body", async () => {
    getCurrentUserMock.mockResolvedValue({ data: { id: "user-1" }, error: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });

    const request = new Request("http://localhost/api/businesses/biz-1/research/competitors", {
      method: "POST",
      body: "{not valid json",
      headers: { "Content-Type": "application/json" },
    });

    const response = await POST(request, makeParams("biz-1"));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("invalid_json");
    expect(createResearchCompetitorMock).not.toHaveBeenCalled();
  });
});

describe("PATCH /api/businesses/[id]/research/competitors", () => {
  beforeEach(() => {
    getCurrentUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    createResearchCompetitorMock.mockReset();
    updateResearchCompetitorMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("updates the competitor when authenticated and owning the business", async () => {
    getCurrentUserMock.mockResolvedValue({ data: { id: "user-1" }, error: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    updateResearchCompetitorMock.mockResolvedValue({ data: { id: "comp-1" }, error: null });

    const response = await PATCH(
      makeRequest("PATCH", { id: "comp-1", name: "Updated Name" }),
      makeParams("biz-1"),
    );

    expect(response.status).toBe(200);
    expect(updateResearchCompetitorMock).toHaveBeenCalledWith(
      expect.objectContaining({ id: "comp-1", business_id: "biz-1" }),
    );
  });

  it("returns a 400 validation_error envelope and never updates when id is missing", async () => {
    getCurrentUserMock.mockResolvedValue({ data: { id: "user-1" }, error: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });

    const response = await PATCH(
      makeRequest("PATCH", { name: "Updated Name" }),
      makeParams("biz-1"),
    );

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.id).toBeDefined();
    expect(updateResearchCompetitorMock).not.toHaveBeenCalled();
  });
});
