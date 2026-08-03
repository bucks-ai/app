import { describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@supabase/ssr", () => ({
  createServerClient: vi.fn(() => ({
    auth: { getUser: vi.fn().mockResolvedValue({ data: { user: null } }) },
  })),
}));

import { middleware } from "../middleware";

function expectSecurityHeaders(response: Response) {
  expect(response.headers.get("X-Frame-Options")).toBe("DENY");
  expect(response.headers.get("X-Content-Type-Options")).toBe("nosniff");
  expect(response.headers.get("Referrer-Policy")).toBe(
    "strict-origin-when-cross-origin",
  );

  const csp = response.headers.get("Content-Security-Policy-Report-Only");
  expect(csp).toBeTruthy();
  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain("frame-ancestors 'none'");

  // CSP must stay report-only for this task — enforcing mode is a follow-up.
  expect(response.headers.get("Content-Security-Policy")).toBeNull();
}

describe("middleware security headers", () => {
  it("sets security headers on a page response", async () => {
    const request = new NextRequest("http://localhost:3000/dashboard");
    const response = await middleware(request);
    expectSecurityHeaders(response);
  });

  it("sets security headers on an API response", async () => {
    const request = new NextRequest("http://localhost:3000/api/businesses");
    const response = await middleware(request);
    expectSecurityHeaders(response);
  });
});
