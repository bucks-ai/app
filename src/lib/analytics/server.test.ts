import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { captureMock, flushMock, postHogConstructorMock, afterMock } = vi.hoisted(() => ({
  captureMock: vi.fn(),
  flushMock: vi.fn().mockResolvedValue(undefined),
  postHogConstructorMock: vi.fn(),
  afterMock: vi.fn(),
}));

vi.mock("posthog-node", () => ({
  PostHog: class {
    constructor(...args: unknown[]) {
      postHogConstructorMock(...args);
    }
    capture = captureMock;
    flush = flushMock;
  },
}));

vi.mock("next/server", () => ({
  after: afterMock,
}));

async function importFreshServerModule() {
  vi.resetModules();
  return import("./server");
}

const testUser = { id: "user-1", email: "founder@example.com" };

describe("analytics server capture", () => {
  const originalKey = process.env.POSTHOG_KEY;
  const originalHost = process.env.POSTHOG_HOST;
  const originalE2E = process.env.E2E_FAKE_AI;
  const originalVerify = process.env.M3_VERIFY;
  const originalTestEmail = process.env.TEST_USER_EMAIL;

  beforeEach(() => {
    captureMock.mockReset();
    flushMock.mockReset().mockResolvedValue(undefined);
    postHogConstructorMock.mockReset();
    afterMock.mockReset();
    delete process.env.POSTHOG_KEY;
    delete process.env.POSTHOG_HOST;
    delete process.env.E2E_FAKE_AI;
    delete process.env.M3_VERIFY;
    delete process.env.TEST_USER_EMAIL;
  });

  afterEach(() => {
    if (originalKey === undefined) delete process.env.POSTHOG_KEY;
    else process.env.POSTHOG_KEY = originalKey;
    if (originalHost === undefined) delete process.env.POSTHOG_HOST;
    else process.env.POSTHOG_HOST = originalHost;
    if (originalE2E === undefined) delete process.env.E2E_FAKE_AI;
    else process.env.E2E_FAKE_AI = originalE2E;
    if (originalVerify === undefined) delete process.env.M3_VERIFY;
    else process.env.M3_VERIFY = originalVerify;
    if (originalTestEmail === undefined) delete process.env.TEST_USER_EMAIL;
    else process.env.TEST_USER_EMAIL = originalTestEmail;
  });

  it("is a complete no-op when POSTHOG_KEY is unset", async () => {
    const { capture } = await importFreshServerModule();

    expect(() => capture("BLUEPRINT_GENERATED", testUser, {})).not.toThrow();

    expect(postHogConstructorMock).not.toHaveBeenCalled();
    expect(captureMock).not.toHaveBeenCalled();
    expect(afterMock).not.toHaveBeenCalled();
  });

  it("constructs the client once and forwards distinctId/event/properties when POSTHOG_KEY is set", async () => {
    process.env.POSTHOG_KEY = "phc_test_key";
    const { capture } = await importFreshServerModule();

    capture("BLUEPRINT_SAVED", testUser, { business_id: "biz-1" });

    expect(postHogConstructorMock).toHaveBeenCalledTimes(1);
    expect(postHogConstructorMock).toHaveBeenCalledWith(
      "phc_test_key",
      expect.objectContaining({ host: expect.any(String) }),
    );
    expect(captureMock).toHaveBeenCalledWith({
      distinctId: "user-1",
      event: "blueprint_saved",
      properties: { business_id: "biz-1" },
    });

    capture("TOOL_APPROVED", testUser, { business_id: "biz-1" });
    expect(postHogConstructorMock).toHaveBeenCalledTimes(1);
  });

  it("uses POSTHOG_HOST when provided", async () => {
    process.env.POSTHOG_KEY = "phc_test_key";
    process.env.POSTHOG_HOST = "https://eu.i.posthog.com";
    const { capture } = await importFreshServerModule();

    capture("REPO_CREATED", testUser, { business_id: "biz-1" });

    expect(postHogConstructorMock).toHaveBeenCalledWith(
      "phc_test_key",
      expect.objectContaining({ host: "https://eu.i.posthog.com" }),
    );
  });

  it("schedules a flush via after() instead of blocking the caller", async () => {
    process.env.POSTHOG_KEY = "phc_test_key";
    const { capture } = await importFreshServerModule();

    capture("SCAFFOLD_PREPARED", testUser, { business_id: "biz-1" });

    expect(afterMock).toHaveBeenCalledTimes(1);
    expect(flushMock).not.toHaveBeenCalled();

    const scheduled = afterMock.mock.calls[0][0] as () => Promise<void>;
    await scheduled();
    expect(flushMock).toHaveBeenCalledTimes(1);
  });

  it("never throws when the underlying client's capture() throws", async () => {
    process.env.POSTHOG_KEY = "phc_test_key";
    captureMock.mockImplementation(() => {
      throw new Error("network is down");
    });
    const { capture } = await importFreshServerModule();

    expect(() => capture("VERCEL_PROJECT_CREATED", testUser, { business_id: "biz-1" })).not.toThrow();
    expect(afterMock).not.toHaveBeenCalled();
  });

  it("never throws when the scheduled flush rejects", async () => {
    process.env.POSTHOG_KEY = "phc_test_key";
    flushMock.mockRejectedValue(new Error("flush failed"));
    const { capture } = await importFreshServerModule();

    capture("DEPLOY_SUCCEEDED", testUser, { business_id: "biz-1" });

    const scheduled = afterMock.mock.calls[0][0] as () => Promise<void>;
    await expect(scheduled()).resolves.toBeUndefined();
  });

  it.each([
    ["TOOL_APPROVAL_REQUESTED", "tool_approval_requested"],
    ["TOOL_APPROVED", "tool_approved"],
    ["REPO_CREATED", "repo_created"],
    ["SCAFFOLD_PREPARED", "scaffold_prepared"],
    ["VERCEL_PROJECT_CREATED", "vercel_project_created"],
    ["DEPLOY_SUCCEEDED", "deploy_succeeded"],
    ["BLUEPRINT_GENERATED", "blueprint_generated"],
    ["BLUEPRINT_SAVED", "blueprint_saved"],
  ] as const)("captures the canonical event name for %s", async (eventKey, eventName) => {
    process.env.POSTHOG_KEY = "phc_test_key";
    const { capture } = await importFreshServerModule();

    capture(eventKey, testUser, { business_id: "biz-1" });

    expect(captureMock).toHaveBeenCalledWith(
      expect.objectContaining({ event: eventName }),
    );
  });

  describe("test-traffic guard", () => {
    it("no-ops for E2E test traffic and never constructs a client", async () => {
      process.env.POSTHOG_KEY = "phc_test_key";
      process.env.E2E_FAKE_AI = "true";
      const { capture } = await importFreshServerModule();

      capture("BLUEPRINT_SAVED", testUser, { business_id: "biz-1" });

      expect(postHogConstructorMock).not.toHaveBeenCalled();
      expect(captureMock).not.toHaveBeenCalled();
    });

    it("no-ops for the seeded TEST_USER_EMAIL user", async () => {
      process.env.POSTHOG_KEY = "phc_test_key";
      process.env.TEST_USER_EMAIL = testUser.email;
      const { capture } = await importFreshServerModule();

      capture("BLUEPRINT_SAVED", testUser, { business_id: "biz-1" });

      expect(postHogConstructorMock).not.toHaveBeenCalled();
      expect(captureMock).not.toHaveBeenCalled();
    });

    it("re-enables capture and stamps verification_run when M3_VERIFY=true", async () => {
      process.env.POSTHOG_KEY = "phc_test_key";
      process.env.E2E_FAKE_AI = "true";
      process.env.M3_VERIFY = "true";
      const { capture } = await importFreshServerModule();

      capture("BLUEPRINT_SAVED", testUser, { business_id: "biz-1" });

      expect(captureMock).toHaveBeenCalledWith({
        distinctId: "user-1",
        event: "blueprint_saved",
        properties: { business_id: "biz-1", verification_run: true },
      });
    });
  });
});
