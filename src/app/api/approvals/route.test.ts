import { beforeEach, describe, expect, it, vi } from "vitest";

const { requireUserMock, hasSupabaseEnvMock, getPendingApprovalsForOwnerMock } = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getPendingApprovalsForOwnerMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/approvals", () => ({
  getPendingApprovalsForOwner: getPendingApprovalsForOwnerMock,
}));

import { GET } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

describe("GET /api/approvals", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getPendingApprovalsForOwnerMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns 503 when Supabase is not configured", async () => {
    hasSupabaseEnvMock.mockReturnValue(false);

    const response = await GET();

    expect(response.status).toBe(503);
    expect(requireUserMock).not.toHaveBeenCalled();
  });

  it("returns the standard 401 envelope when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await GET();

    expect(response.status).toBe(401);
    expect(getPendingApprovalsForOwnerMock).not.toHaveBeenCalled();
  });

  it("lists the authenticated owner's pending approvals", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getPendingApprovalsForOwnerMock.mockResolvedValue({
      data: [{ id: "approval-1", request_type: "merge_approval", status: "pending" }],
      error: null,
    });

    const response = await GET();

    expect(getPendingApprovalsForOwnerMock).toHaveBeenCalledWith("user-1");
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      data: { approvals: [{ id: "approval-1", request_type: "merge_approval", status: "pending" }] },
    });
  });

  it("degrades to an empty list when the approvals table doesn't exist yet", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getPendingApprovalsForOwnerMock.mockResolvedValue({
      data: null,
      error: "approvals table does not exist.",
      code: "approvals_schema_missing",
    });

    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true, data: { approvals: [] } });
  });

  it("returns a 500 envelope for other fetch failures", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getPendingApprovalsForOwnerMock.mockResolvedValue({
      data: null,
      error: "boom",
      code: "approvals_fetch_failed",
    });

    const response = await GET();

    expect(response.status).toBe(500);
    const payload = await response.json();
    expect(payload.code).toBe("approvals_fetch_failed");
  });
});
