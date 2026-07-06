import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  createValidationLeadMock,
  updateValidationLeadMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  createValidationLeadMock: vi.fn(),
  updateValidationLeadMock: vi.fn(),
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
  createValidationLead: createValidationLeadMock,
  updateValidationLead: updateValidationLeadMock,
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
  return new Request("http://localhost/api/businesses/biz-1/validation/leads", {
    method,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("POST /api/businesses/[id]/validation/leads", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    createValidationLeadMock.mockReset();
    updateValidationLeadMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  const validBody = { name: "Jane Prospect" };

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
    expect(createValidationLeadMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await POST(makeRequest("POST", validBody), makeParams("biz-1"));

    expect(response.status).toBe(404);
    expect(createValidationLeadMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await POST(makeRequest("POST", validBody), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(createValidationLeadMock).not.toHaveBeenCalled();
  });

  it("creates the lead scoped to the authenticated user when authorized", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    createValidationLeadMock.mockResolvedValue({ data: { id: "lead-1" }, error: null });

    const response = await POST(makeRequest("POST", validBody), makeParams("biz-1"));

    expect(response.status).toBe(201);
    expect(createValidationLeadMock).toHaveBeenCalledWith(
      expect.objectContaining({ business_id: "biz-1", user_id: "user-1", name: validBody.name }),
    );
  });
});

describe("PATCH /api/businesses/[id]/validation/leads", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    createValidationLeadMock.mockReset();
    updateValidationLeadMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  const validBody = { id: "lead-1", name: "Updated Name" };

  it("returns the standard 401 envelope and never updates when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse });

    const response = await PATCH(makeRequest("PATCH", validBody), makeParams("biz-1"));

    expect(response.status).toBe(401);
    expect(updateValidationLeadMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await PATCH(makeRequest("PATCH", validBody), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(updateValidationLeadMock).not.toHaveBeenCalled();
  });

  it("updates the lead when authenticated and owning the business", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    updateValidationLeadMock.mockResolvedValue({ data: { id: "lead-1" }, error: null });

    const response = await PATCH(makeRequest("PATCH", validBody), makeParams("biz-1"));

    expect(response.status).toBe(200);
    expect(updateValidationLeadMock).toHaveBeenCalledWith(
      expect.objectContaining({ id: "lead-1", business_id: "biz-1" }),
    );
  });
});
