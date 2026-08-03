import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { guardCapture, isTestTraffic, isVerifyRunEnabled } from "./guard";

const ENV_KEYS = [
  "E2E_FAKE_AI",
  "NEXT_PUBLIC_E2E_FAKE_AI",
  "M3_VERIFY",
  "NEXT_PUBLIC_M3_VERIFY",
  "TEST_USER_EMAIL",
  "VERCEL",
  "E2E_FAKE_AI_ALLOW_PRODUCTION_BUILD",
] as const;

describe("analytics test-traffic guard", () => {
  const original: Record<string, string | undefined> = {};

  beforeEach(() => {
    for (const key of ENV_KEYS) {
      original[key] = process.env[key];
      delete process.env[key];
    }
    vi.stubEnv("NODE_ENV", "test");
  });

  afterEach(() => {
    for (const key of ENV_KEYS) {
      if (original[key] === undefined) delete process.env[key];
      else process.env[key] = original[key];
    }
    vi.unstubAllEnvs();
  });

  describe("isVerifyRunEnabled", () => {
    it("is false by default", () => {
      expect(isVerifyRunEnabled()).toBe(false);
    });

    it("is true when M3_VERIFY=true", () => {
      process.env.M3_VERIFY = "true";
      expect(isVerifyRunEnabled()).toBe(true);
    });

    it("is true when NEXT_PUBLIC_M3_VERIFY=true", () => {
      process.env.NEXT_PUBLIC_M3_VERIFY = "true";
      expect(isVerifyRunEnabled()).toBe(true);
    });

    it("is false for any value other than exactly \"true\"", () => {
      process.env.M3_VERIFY = "1";
      expect(isVerifyRunEnabled()).toBe(false);
    });
  });

  describe("isTestTraffic", () => {
    it("is false when nothing is configured", () => {
      expect(isTestTraffic("founder@example.com")).toBe(false);
      expect(isTestTraffic(undefined)).toBe(false);
    });

    it("is true when E2E_FAKE_AI=true", () => {
      process.env.E2E_FAKE_AI = "true";
      expect(isTestTraffic("founder@example.com")).toBe(true);
    });

    it("is true when NEXT_PUBLIC_E2E_FAKE_AI=true (client-bundle mirror)", () => {
      process.env.NEXT_PUBLIC_E2E_FAKE_AI = "true";
      expect(isTestTraffic(undefined)).toBe(true);
    });

    it("is true when the email matches TEST_USER_EMAIL", () => {
      process.env.TEST_USER_EMAIL = "qa@bucks.ai";
      expect(isTestTraffic("qa@bucks.ai")).toBe(true);
    });

    it("is false when the email does not match TEST_USER_EMAIL", () => {
      process.env.TEST_USER_EMAIL = "qa@bucks.ai";
      expect(isTestTraffic("founder@example.com")).toBe(false);
    });

    it("is false when TEST_USER_EMAIL is set but no email is given", () => {
      process.env.TEST_USER_EMAIL = "qa@bucks.ai";
      expect(isTestTraffic(undefined)).toBe(false);
      expect(isTestTraffic(null)).toBe(false);
    });
  });

  describe("guardCapture", () => {
    it("allows capture unchanged when traffic is not test traffic and verify is off", () => {
      const result = guardCapture("founder@example.com", { business_id: "biz-1" });
      expect(result).toEqual({ allow: true, properties: { business_id: "biz-1" } });
    });

    it("drops capture entirely for E2E test traffic when verify is off", () => {
      process.env.E2E_FAKE_AI = "true";
      const result = guardCapture("founder@example.com", { business_id: "biz-1" });
      expect(result.allow).toBe(false);
    });

    it("drops capture entirely for the seeded test user when verify is off", () => {
      process.env.TEST_USER_EMAIL = "qa@bucks.ai";
      const result = guardCapture("qa@bucks.ai", { business_id: "biz-1" });
      expect(result.allow).toBe(false);
    });

    it("re-enables capture and stamps verification_run for test traffic when M3_VERIFY=true", () => {
      process.env.E2E_FAKE_AI = "true";
      process.env.M3_VERIFY = "true";
      const result = guardCapture("founder@example.com", { business_id: "biz-1" });
      expect(result).toEqual({
        allow: true,
        properties: { business_id: "biz-1", verification_run: true },
      });
    });

    it("stamps verification_run on every event when M3_VERIFY=true, even for non-test traffic", () => {
      process.env.M3_VERIFY = "true";
      const result = guardCapture("founder@example.com", { business_id: "biz-1" });
      expect(result).toEqual({
        allow: true,
        properties: { business_id: "biz-1", verification_run: true },
      });
    });

    it("defaults properties to an empty object", () => {
      expect(guardCapture("founder@example.com")).toEqual({ allow: true, properties: {} });
    });
  });
});
