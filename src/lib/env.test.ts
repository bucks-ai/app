import { describe, expect, it } from "vitest";
import { validateEnv } from "./env";

const validEnv: Record<string, string> = {
  SUPABASE_URL: "https://project.supabase.co",
  SUPABASE_SERVICE_ROLE_KEY: "service-role-key",
  OPENAI_API_KEY: "sk-test",
  GITHUB_TOKEN: "ghp-test",
  VERCEL_TOKEN: "vercel-test",
  VERCEL_PROJECT_ID: "prj_test",
  NEXT_PUBLIC_SUPABASE_URL: "https://project.supabase.co",
  NEXT_PUBLIC_SUPABASE_ANON_KEY: "anon-key",
};

function withoutKeys(...keys: string[]): Record<string, string> {
  const copy = { ...validEnv };
  for (const key of keys) delete copy[key];
  return copy;
}

describe("validateEnv", () => {
  it("returns parsed server and client env when all vars are valid", () => {
    const { server, client } = validateEnv(validEnv);

    expect(server).toEqual({
      SUPABASE_URL: validEnv.SUPABASE_URL,
      SUPABASE_SERVICE_ROLE_KEY: validEnv.SUPABASE_SERVICE_ROLE_KEY,
      OPENAI_API_KEY: validEnv.OPENAI_API_KEY,
      GITHUB_TOKEN: validEnv.GITHUB_TOKEN,
      VERCEL_TOKEN: validEnv.VERCEL_TOKEN,
      VERCEL_PROJECT_ID: validEnv.VERCEL_PROJECT_ID,
    });
    expect(client).toEqual({
      NEXT_PUBLIC_SUPABASE_URL: validEnv.NEXT_PUBLIC_SUPABASE_URL,
      NEXT_PUBLIC_SUPABASE_ANON_KEY: validEnv.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    });
  });

  it("throws when a server-only var is missing", () => {
    expect(() => validateEnv(withoutKeys("OPENAI_API_KEY"))).toThrow(
      /OPENAI_API_KEY/
    );
  });

  it("throws when a client var is missing", () => {
    expect(() =>
      validateEnv(withoutKeys("NEXT_PUBLIC_SUPABASE_ANON_KEY"))
    ).toThrow(/NEXT_PUBLIC_SUPABASE_ANON_KEY/);
  });

  it("throws when a URL var is malformed", () => {
    expect(() =>
      validateEnv({ ...validEnv, SUPABASE_URL: "not-a-url" })
    ).toThrow(/SUPABASE_URL/);
  });

  it("lists every missing or invalid var in a single error", () => {
    const partial = withoutKeys("OPENAI_API_KEY", "GITHUB_TOKEN");

    try {
      validateEnv({ ...partial, NEXT_PUBLIC_SUPABASE_URL: "not-a-url" });
      expect.unreachable("validateEnv should have thrown");
    } catch (error) {
      const message = (error as Error).message;
      expect(message).toContain("OPENAI_API_KEY");
      expect(message).toContain("GITHUB_TOKEN");
      expect(message).toContain("NEXT_PUBLIC_SUPABASE_URL");
    }
  });

  it("does not require vars beyond the documented list", () => {
    const { server, client } = validateEnv(validEnv);
    expect(Object.keys(server).sort()).toEqual(
      [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "OPENAI_API_KEY",
        "GITHUB_TOKEN",
        "VERCEL_TOKEN",
        "VERCEL_PROJECT_ID",
      ].sort()
    );
    expect(Object.keys(client).sort()).toEqual(
      ["NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY"].sort()
    );
  });
});

describe("module load with process.env", () => {
  it("does not throw when all required vars are present (current environment)", async () => {
    await expect(import("./env")).resolves.toBeDefined();
  });
});
