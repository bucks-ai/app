import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const { requireUserMock, hasSupabaseEnvMock, updateApprovalDecisionMock } = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  updateApprovalDecisionMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/approvals", () => ({
  updateApprovalDecision: updateApprovalDecisionMock,
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
  return new NextRequest("http://localhost/api/approvals/approval-1", {
    method: "PATCH",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("PATCH /api/approvals/[id]", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    updateApprovalDecisionMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never calls updateApprovalDecision when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await PATCH(makeRequest({ action: "approve" }), makeParams("approval-1"));

    expect(response.status).toBe(401);
    expect(updateApprovalDecisionMock).not.toHaveBeenCalled();
  });

  it("updates the approval when authenticated and owning the record", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1", email: "founder@example.com" }, response: null });
    updateApprovalDecisionMock.mockResolvedValue({
      data: { id: "approval-1", status: "approved" },
      error: null,
    });

    const response = await PATCH(makeRequest({ action: "approve" }), makeParams("approval-1"));

    expect(response.status).toBe(200);
    expect(updateApprovalDecisionMock).toHaveBeenCalledWith({
      id: "approval-1",
      action: "approve",
      userId: "user-1",
      decidedBy: "founder@example.com",
    });
    await expect(response.json()).resolves.toEqual({
      ok: true,
      data: { id: "approval-1", status: "approved" },
    });
  });

  it("falls back to userId for decidedBy when the user has no email", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1", email: null }, response: null });
    updateApprovalDecisionMock.mockResolvedValue({
      data: { id: "approval-1", status: "rejected" },
      error: null,
    });

    await PATCH(makeRequest({ action: "reject" }), makeParams("approval-1"));

    expect(updateApprovalDecisionMock).toHaveBeenCalledWith({
      id: "approval-1",
      action: "reject",
      userId: "user-1",
      decidedBy: "user-1",
    });
  });

  it("returns 404 when the approval does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    updateApprovalDecisionMock.mockResolvedValue({ data: null, error: "not found", code: "not_found" });

    const response = await PATCH(makeRequest({ action: "approve" }), makeParams("approval-1"));

    expect(response.status).toBe(404);
  });

  it("returns 403 when the approval belongs to another user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    updateApprovalDecisionMock.mockResolvedValue({ data: null, error: "Forbidden.", code: "forbidden" });

    const response = await PATCH(makeRequest({ action: "approve" }), makeParams("approval-1"));

    expect(response.status).toBe(403);
  });

  it("returns a 400 badRequest envelope when action is missing", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });

    const response = await PATCH(makeRequest({}), makeParams("approval-1"));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("validation_error");
    expect(updateApprovalDecisionMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope when action is not approve/reject", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });

    const response = await PATCH(makeRequest({ action: "delete" }), makeParams("approval-1"));

    expect(response.status).toBe(400);
    expect(updateApprovalDecisionMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope for malformed JSON", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });

    const request = new NextRequest("http://localhost/api/approvals/approval-1", {
      method: "PATCH",
      body: "{not valid json",
      headers: { "Content-Type": "application/json" },
    });

    const response = await PATCH(request, makeParams("approval-1"));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("invalid_json");
  });
});
