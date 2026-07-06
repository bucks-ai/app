// Route auth inventory guard.
//
// Programmatically enumerates every route.ts file under src/app/api/ and
// asserts that each exported HTTP handler rejects an unauthenticated request
// with the standard 401 envelope: { ok: false, error: "Authentication
// required.", code: "unauthenticated" }.
//
// The Supabase server client is mocked once, at the module boundary shared by
// both auth entry points (`requireUser()` in src/lib/api-auth.ts and the
// older `getCurrentUser()` in src/lib/projects.ts), so this test is agnostic
// to which pattern a given route uses.
//
// A route is added to PUBLIC_ROUTE_ALLOWLIST only when it is deliberately
// reachable without authentication. It starts empty: every route today
// requires auth, and any future route that doesn't will fail this test until
// someone makes that exemption explicit and reviewed.

import { readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: async () => ({
    auth: {
      getUser: async () => ({ data: { user: null }, error: null }),
    },
  }),
}));

const API_DIR = path.dirname(fileURLToPath(import.meta.url));
const HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const;

const EXPECTED_ENVELOPE = {
  ok: false,
  error: "Authentication required.",
  code: "unauthenticated",
};

// Routes exempt from this guard because they are intentionally public.
// Keep empty unless a route is deliberately meant to be reachable without
// authentication — adding an entry here should be a reviewed decision.
const PUBLIC_ROUTE_ALLOWLIST: string[] = [];

// Some handlers parse a businessId (query string or JSON body) before
// checking auth. Supply whatever is needed to reach the auth check —
// the value itself is never used since the request is rejected first.
type RouteRequestConfig = {
  query?: Record<string, string>;
  body?: Record<string, unknown>;
};

const TEST_BUSINESS_ID = "test-business-id";

const ROUTE_REQUEST_CONFIG: Record<string, RouteRequestConfig> = {
  "github/create-repo/route.ts": { body: { businessId: TEST_BUSINESS_ID } },
  "github/prepare-next-scaffold/route.ts": {
    body: { businessId: TEST_BUSINESS_ID },
  },
  "tool-permissions/route.ts": {
    query: { businessId: TEST_BUSINESS_ID },
    body: { businessId: TEST_BUSINESS_ID },
  },
  "vercel/create-project/route.ts": { body: { businessId: TEST_BUSINESS_ID } },
  "vercel/deploy-gate/route.ts": { query: { businessId: TEST_BUSINESS_ID } },
  "vercel/project-status/route.ts": {
    query: { businessId: TEST_BUSINESS_ID },
  },
  "vercel/refresh-deployment-status/route.ts": {
    body: { businessId: TEST_BUSINESS_ID },
  },
};

function findRouteFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findRouteFiles(fullPath));
    } else if (entry.isFile() && entry.name === "route.ts") {
      files.push(fullPath);
    }
  }
  return files;
}

function toRelPath(filePath: string): string {
  return path.relative(API_DIR, filePath).split(path.sep).join("/");
}

// Dynamic segments (e.g. "[id]") get a placeholder value — routes only
// check that the value is present, never what it is, before the auth check.
function extractDynamicParams(relPath: string): Record<string, string> {
  const params: Record<string, string> = {};
  for (const match of relPath.matchAll(/\[([^\]]+)\]/g)) {
    params[match[1]] = `test-${match[1]}`;
  }
  return params;
}

function buildRequest(
  relPath: string,
  method: string,
  config: RouteRequestConfig
): Request {
  const routePath =
    "/api/" + relPath.replace(/\/route\.ts$/, "").replace(/\[([^\]]+)\]/g, "test-$1");
  const url = new URL(routePath, "http://localhost");

  if (method === "GET") {
    if (config.query) {
      for (const [key, value] of Object.entries(config.query)) {
        url.searchParams.set(key, value);
      }
    }
    return new Request(url, { method });
  }

  return new Request(url, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(config.body ?? {}),
  });
}

describe("route auth inventory", () => {
  beforeAll(() => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "test-anon-key");
    vi.stubEnv("GITHUB_PERSONAL_ACCESS_TOKEN", "test-github-token");
    vi.stubEnv("VERCEL_TOKEN", "test-vercel-token");
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  const routeFiles = findRouteFiles(API_DIR);

  it("finds route.ts files under src/app/api to check", () => {
    expect(routeFiles.length).toBeGreaterThan(0);
  });

  for (const filePath of routeFiles) {
    const relPath = toRelPath(filePath);

    if (PUBLIC_ROUTE_ALLOWLIST.includes(relPath)) {
      it.skip(`${relPath} — allowlisted as intentionally public`, () => {});
      continue;
    }

    it(`${relPath} rejects unauthenticated requests with the standard 401 envelope`, async () => {
      const mod = await import(filePath);
      const config = ROUTE_REQUEST_CONFIG[relPath] ?? {};
      const params = extractDynamicParams(relPath);
      const methodsPresent = HTTP_METHODS.filter(
        (method) => typeof mod[method] === "function"
      );

      expect(
        methodsPresent.length,
        `${relPath} exports no recognized HTTP method handler (checked ${HTTP_METHODS.join(", ")})`
      ).toBeGreaterThan(0);

      for (const method of methodsPresent) {
        const request = buildRequest(relPath, method, config);
        const context = { params: Promise.resolve(params) };

        const response: Response = await mod[method](request, context);

        expect(
          response.status,
          `${method} ${relPath} should return 401 when unauthenticated`
        ).toBe(401);
        await expect(
          response.json(),
          `${method} ${relPath} should return the standard 401 envelope`
        ).resolves.toEqual(EXPECTED_ENVELOPE);
      }
    });
  }
});
