import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  getBusinessByIdMock,
  getSandboxConfigForBusinessMock,
  upsertSandboxConfigMock,
  limitMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  getBusinessByIdMock: vi.fn(),
  getSandboxConfigForBusinessMock: vi.fn(),
  upsertSandboxConfigMock: vi.fn(),
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
}));

vi.mock("@/lib/sandbox", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/sandbox")>();
  return {
    ...actual,
    getSandboxConfigForBusiness: getSandboxConfigForBusinessMock,
    upsertSandboxConfig: upsertSandboxConfigMock,
  };
});

import { GET, PATCH } from "./route";

function unauthorizedResponse() {
  return Response.json(
    { ok: false, error: "Authentication required.", code: "unauthenticated" },
    { status: 401 },
  );
}

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

function makePatchRequest(body: unknown) {
  return new Request("http://localhost/api/businesses/biz-1/sandbox", {
    method: "PATCH",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

const OWNED_BUSINESS = { id: "biz-1", user_id: "user-1", idea_name: "Acme" };

const SANDBOX_RECORD = {
  id: "sandbox-1",
  business_id: "biz-1",
  user_id: "user-1",
  repo_full_name: "acme/landing-page",
  vercel_project_id: null,
  github_token_secret_name: null,
  vercel_token_secret_name: null,
  status: "partial",
  created_at: "2026-07-01T00:00:00.000Z",
  updated_at: "2026-07-01T00:00:00.000Z",
};

describe("GET /api/businesses/[id]/sandbox", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getSandboxConfigForBusinessMock.mockReset();
    upsertSandboxConfigMock.mockReset();
    limitMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    limitMock.mockResolvedValue({ allowed: true, remaining: 29 });
  });

  it("returns the standard 401 envelope and never queries the business when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(401);
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(getSandboxConfigForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 404 when the business does not exist", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: null, error: "not found" });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(404);
    expect(getSandboxConfigForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to a different user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-2" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(403);
    expect(getSandboxConfigForBusinessMock).not.toHaveBeenCalled();
  });

  it("returns unconfigured status with every field unconfigured when no sandbox row exists", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });
    getSandboxConfigForBusinessMock.mockResolvedValue({ data: null, error: null });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload.ok).toBe(true);
    expect(payload.data.sandbox.status).toBe("unconfigured");
    expect(payload.data.sandbox.fields).toHaveLength(4);
    expect(payload.data.sandbox.fields.every((f: { configured: boolean }) => f.configured === false)).toBe(true);
  });

  it("returns the sandbox record's status and per-field breakdown, values as names only", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });
    getSandboxConfigForBusinessMock.mockResolvedValue({ data: SANDBOX_RECORD, error: null });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload.data.sandbox.status).toBe("partial");
    const repoField = payload.data.sandbox.fields.find(
      (f: { field: string }) => f.field === "repo_full_name"
    );
    expect(repoField).toMatchObject({ configured: true, value: "acme/landing-page" });
  });

  it("returns a 500 envelope when the sandbox fetch fails", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });
    getSandboxConfigForBusinessMock.mockResolvedValue({ data: null, error: "db error" });

    const response = await GET(new Request("http://localhost"), makeParams("biz-1"));

    expect(response.status).toBe(500);
  });
});

describe("PATCH /api/businesses/[id]/sandbox", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    getBusinessByIdMock.mockReset();
    getSandboxConfigForBusinessMock.mockReset();
    upsertSandboxConfigMock.mockReset();
    limitMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    limitMock.mockResolvedValue({ allowed: true, remaining: 29 });
  });

  it("returns the standard 401 envelope and never upserts when unauthenticated", async () => {
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse() });

    const response = await PATCH(makePatchRequest({ repo_full_name: "acme/x" }), makeParams("biz-1"));

    expect(response.status).toBe(401);
    expect(upsertSandboxConfigMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope when the body has no recognised fields", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });

    const response = await PATCH(makePatchRequest({}), makeParams("biz-1"));

    expect(response.status).toBe(400);
    expect(upsertSandboxConfigMock).not.toHaveBeenCalled();
  });

  it("returns the standard 429 envelope when the rate limit is exceeded", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    limitMock.mockResolvedValue({ allowed: false, remaining: 0 });

    const response = await PATCH(
      makePatchRequest({ repo_full_name: "acme/landing-page" }),
      makeParams("biz-1")
    );

    expect(response.status).toBe(429);
    expect(getBusinessByIdMock).not.toHaveBeenCalled();
    expect(upsertSandboxConfigMock).not.toHaveBeenCalled();
  });

  it("returns 403 when the business belongs to a different user", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-2" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });

    const response = await PATCH(
      makePatchRequest({ repo_full_name: "acme/landing-page" }),
      makeParams("biz-1")
    );

    expect(response.status).toBe(403);
    expect(upsertSandboxConfigMock).not.toHaveBeenCalled();
  });

  it("upserts the sandbox config and returns the updated status on success", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });
    upsertSandboxConfigMock.mockResolvedValue({ data: SANDBOX_RECORD, error: null });

    const response = await PATCH(
      makePatchRequest({ repo_full_name: "acme/landing-page" }),
      makeParams("biz-1")
    );

    expect(response.status).toBe(200);
    expect(upsertSandboxConfigMock).toHaveBeenCalledWith("biz-1", "user-1", {
      repo_full_name: "acme/landing-page",
    });
    const payload = await response.json();
    expect(payload.data.sandbox.status).toBe("partial");
  });

  it("returns a 500 envelope when the upsert fails", async () => {
    requireUserMock.mockResolvedValue({ user: { id: "user-1" }, response: null });
    getBusinessByIdMock.mockResolvedValue({ data: OWNED_BUSINESS, error: null });
    upsertSandboxConfigMock.mockResolvedValue({ data: null, error: "db error" });

    const response = await PATCH(
      makePatchRequest({ repo_full_name: "acme/landing-page" }),
      makeParams("biz-1")
    );

    expect(response.status).toBe(500);
  });
});
