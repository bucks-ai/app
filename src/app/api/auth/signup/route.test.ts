import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const { createSupabaseServerClientMock, hasSupabaseEnvMock, limitMock, captureMock } = vi.hoisted(
  () => ({
    createSupabaseServerClientMock: vi.fn(),
    hasSupabaseEnvMock: vi.fn(),
    limitMock: vi.fn(),
    captureMock: vi.fn(),
  }),
);

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: createSupabaseServerClientMock,
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/rate-limit", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/rate-limit")>();
  return { ...actual, limit: limitMock };
});

vi.mock("@/lib/analytics/server", () => ({
  capture: captureMock,
}));

import { POST } from "./route";

function makeRequest(body: unknown) {
  return new NextRequest("http://localhost/api/auth/signup", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", "x-forwarded-for": "203.0.113.1" },
  });
}

function signUpMock(result: unknown) {
  return { auth: { signUp: vi.fn().mockResolvedValue(result) } };
}

describe("POST /api/auth/signup", () => {
  beforeEach(() => {
    createSupabaseServerClientMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    limitMock.mockReset();
    captureMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
    limitMock.mockResolvedValue({ allowed: true, remaining: 9 });
  });

  it("returns 503 when Supabase is not configured", async () => {
    hasSupabaseEnvMock.mockReturnValue(false);

    const response = await POST(makeRequest({ email: "a@example.com", password: "password1" }));

    expect(response.status).toBe(503);
    expect(createSupabaseServerClientMock).not.toHaveBeenCalled();
    expect(captureMock).not.toHaveBeenCalled();
  });

  it("returns 429 and never calls signUp when the IP rate limit is exceeded", async () => {
    limitMock.mockResolvedValue({ allowed: false, remaining: 0 });

    const response = await POST(makeRequest({ email: "a@example.com", password: "password1" }));

    expect(response.status).toBe(429);
    expect(createSupabaseServerClientMock).not.toHaveBeenCalled();
    expect(captureMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope for a malformed JSON body", async () => {
    const request = new NextRequest("http://localhost/api/auth/signup", {
      method: "POST",
      body: "{not valid json",
      headers: { "Content-Type": "application/json" },
    });

    const response = await POST(request);

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("invalid_json");
    expect(captureMock).not.toHaveBeenCalled();
  });

  it("returns a 400 validation_error envelope for an invalid email/short password", async () => {
    const response = await POST(makeRequest({ email: "not-an-email", password: "short" }));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.email).toBeDefined();
    expect(payload.issues.password).toBeDefined();
    expect(createSupabaseServerClientMock).not.toHaveBeenCalled();
    expect(captureMock).not.toHaveBeenCalled();
  });

  it("returns a 400 signup_failed envelope when Supabase rejects the signup, without capturing", async () => {
    createSupabaseServerClientMock.mockResolvedValue(
      signUpMock({ data: { user: null, session: null }, error: { message: "User already registered" } }),
    );

    const response = await POST(makeRequest({ email: "a@example.com", password: "password1" }));

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("signup_failed");
    expect(payload.error).toBe("User already registered");
    expect(captureMock).not.toHaveBeenCalled();
  });

  it("captures user_signed_up with signup_method and reports hasSession when autoconfirm is on", async () => {
    createSupabaseServerClientMock.mockResolvedValue(
      signUpMock({
        data: {
          user: { id: "user-1", email: "a@example.com", identities: [{ id: "identity-1" }] },
          session: { access_token: "token" },
        },
        error: null,
      }),
    );

    const response = await POST(makeRequest({ email: "a@example.com", password: "password1" }));

    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload).toEqual({ ok: true, hasSession: true, email: "a@example.com" });
    expect(captureMock).toHaveBeenCalledWith(
      "USER_SIGNED_UP",
      { id: "user-1", email: "a@example.com" },
      { signup_method: "email" },
    );
  });

  it("captures user_signed_up and reports hasSession: false when email confirmation is required", async () => {
    createSupabaseServerClientMock.mockResolvedValue(
      signUpMock({
        data: {
          user: { id: "user-2", email: "b@example.com", identities: [{ id: "identity-2" }] },
          session: null,
        },
        error: null,
      }),
    );

    const response = await POST(makeRequest({ email: "b@example.com", password: "password1" }));

    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload).toEqual({ ok: true, hasSession: false, email: "b@example.com" });
    expect(captureMock).toHaveBeenCalledTimes(1);
  });

  it("does not capture when signUp returns an obfuscated user for an already-registered confirmed email", async () => {
    createSupabaseServerClientMock.mockResolvedValue(
      signUpMock({
        data: {
          user: { id: "fake-id", email: "", identities: [] },
          session: null,
        },
        error: null,
      }),
    );

    const response = await POST(makeRequest({ email: "c@example.com", password: "password1" }));

    expect(response.status).toBe(200);
    expect(captureMock).not.toHaveBeenCalled();
  });
});
