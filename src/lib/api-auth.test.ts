import { beforeEach, describe, expect, it, vi } from "vitest";

const { getUserMock, createSupabaseServerClientMock } = vi.hoisted(() => ({
  getUserMock: vi.fn(),
  createSupabaseServerClientMock: vi.fn(),
}));

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: createSupabaseServerClientMock,
}));

import { requireUser } from "@/lib/api-auth";

describe("requireUser", () => {
  beforeEach(() => {
    getUserMock.mockReset();
    createSupabaseServerClientMock.mockReset();
    createSupabaseServerClientMock.mockResolvedValue({
      auth: { getUser: getUserMock },
    });
  });

  it("returns the authenticated user with no response", async () => {
    getUserMock.mockResolvedValue({
      data: { user: { id: "user-1", email: "a@example.com" } },
      error: null,
    });

    const result = await requireUser();

    expect(result.response).toBeNull();
    expect(result.user?.id).toBe("user-1");
  });

  it("returns a 401 unauthorized envelope when there is no session", async () => {
    getUserMock.mockResolvedValue({ data: { user: null }, error: null });

    const result = await requireUser();

    expect(result.user).toBeNull();
    expect(result.response?.status).toBe(401);
    await expect(result.response?.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
  });

  it("returns a 401 unauthorized envelope when Supabase is not configured", async () => {
    createSupabaseServerClientMock.mockResolvedValue(null);

    const result = await requireUser();

    expect(result.user).toBeNull();
    expect(result.response?.status).toBe(401);
  });
});
