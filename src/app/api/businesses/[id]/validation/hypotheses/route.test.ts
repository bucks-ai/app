import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  createValidationHypothesisMock,
  updateValidationHypothesisMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  createValidationHypothesisMock: vi.fn(),
  updateValidationHypothesisMock: vi.fn(),
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
  createValidationHypothesis: createValidationHypothesisMock,
  updateValidationHypothesis: updateValidationHypothesisMock,
}));

import { POST, PATCH } from "./route";

const unauthorizedResponse = Response.json(
  { ok: false, error: "Authentication required.", code: "unauthenticated" },
  { status: 401 },
);

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

function makeRequest(method: string, body: unknown) {
  return new Request("http://localhost/api/businesses/biz-1/validation/hypotheses", {
    method,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("POST /api/businesses/[id]/validation/hypotheses", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    createValidationHypothesisMock.mockReset();
    updateValidationHypothesisMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  const validBody = { title: "Customers will pay for X" };

  it("returns the standard 401 envelope and never creates when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse });

    const response = await POST(makeRequest("POST", validBody), makeParams("biz-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(createValidationHypothesisMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await POST(makeRequest("POST", validBody), makeParams("biz-1"));

    expect(response.status).toBe(404);
    expect(createValidationHypothesisMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await POST(makeRequest("POST", validBody), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(createValidationHypothesisMock).not.toHaveBeenCalled();
  });

  it("creates the hypothesis scoped to the authenticated user when authorized", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    createValidationHypothesisMock.mockResolvedValue({ data: { id: "hyp-1" }, error: null });

    const response = await POST(makeRequest("POST", validBody), makeParams("biz-1"));

    expect(response.status).toBe(201);
    expect(createValidationHypothesisMock).toHaveBeenCalledWith(
      expect.objectContaining({ business_id: "biz-1", user_id: "user-1", title: validBody.title }),
    );
  });
});

describe("PATCH /api/businesses/[id]/validation/hypotheses", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    createValidationHypothesisMock.mockReset();
    updateValidationHypothesisMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  const validBody = { id: "hyp-1", title: "Updated title" };

  it("returns the standard 401 envelope and never updates when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse });

    const response = await PATCH(makeRequest("PATCH", validBody), makeParams("biz-1"));

    expect(response.status).toBe(401);
    expect(updateValidationHypothesisMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await PATCH(makeRequest("PATCH", validBody), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(updateValidationHypothesisMock).not.toHaveBeenCalled();
  });

  it("updates the hypothesis when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    updateValidationHypothesisMock.mockResolvedValue({ data: { id: "hyp-1" }, error: null });

    const response = await PATCH(makeRequest("PATCH", validBody), makeParams("biz-1"));

    expect(response.status).toBe(200);
    expect(updateValidationHypothesisMock).toHaveBeenCalledWith(
      expect.objectContaining({ id: "hyp-1", business_id: "biz-1" }),
    );
  });
});
