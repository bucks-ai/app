import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  createValidationFeedbackNoteMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  createValidationFeedbackNoteMock: vi.fn(),
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
  createValidationFeedbackNote: createValidationFeedbackNoteMock,
}));

import { POST } from "./route";

const unauthorizedResponse = Response.json(
  { ok: false, error: "Authentication required.", code: "unauthenticated" },
  { status: 401 },
);

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

function makeRequest(body: unknown) {
  return new Request("http://localhost/api/businesses/biz-1/validation/feedback", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

const validBody = { summary: "Great signal from the interview." };

describe("POST /api/businesses/[id]/validation/feedback", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    createValidationFeedbackNoteMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never creates a note when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse });

    const response = await POST(makeRequest(validBody), makeParams("biz-1"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(createValidationFeedbackNoteMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await POST(makeRequest(validBody), makeParams("biz-1"));

    expect(response.status).toBe(404);
    expect(createValidationFeedbackNoteMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "someone-else" }, error: null });

    const response = await POST(makeRequest(validBody), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(createValidationFeedbackNoteMock).not.toHaveBeenCalled();
  });

  it("creates the note scoped to the authenticated user when authorized", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: { id: "biz-1", user_id: "user-1" }, error: null });
    createValidationFeedbackNoteMock.mockResolvedValue({ data: { id: "note-1" }, error: null });

    const response = await POST(makeRequest(validBody), makeParams("biz-1"));

    expect(response.status).toBe(201);
    expect(createValidationFeedbackNoteMock).toHaveBeenCalledWith(
      expect.objectContaining({ business_id: "biz-1", user_id: "user-1", summary: validBody.summary }),
    );
  });
});
