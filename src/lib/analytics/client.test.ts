import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { captureMock } = vi.hoisted(() => ({ captureMock: vi.fn() }));

vi.mock("@/app/posthog", () => ({
  default: { capture: captureMock },
}));

async function importFreshClientModule() {
  vi.resetModules();
  return import("./client");
}

describe("analytics client capture", () => {
  const originalFlag = process.env.E2E_FAKE_AI;
  const originalPublicFlag = process.env.NEXT_PUBLIC_E2E_FAKE_AI;
  const originalVerify = process.env.M3_VERIFY;
  const originalTestEmail = process.env.TEST_USER_EMAIL;
  const originalPublicPosthogKey = process.env.NEXT_PUBLIC_POSTHOG_KEY;

  beforeEach(() => {
    captureMock.mockReset();
    process.env.NEXT_PUBLIC_POSTHOG_KEY = "phc_test";
    delete process.env.E2E_FAKE_AI;
    delete process.env.NEXT_PUBLIC_E2E_FAKE_AI;
    delete process.env.M3_VERIFY;
    delete process.env.TEST_USER_EMAIL;
  });

  afterEach(() => {
    if (originalFlag === undefined) delete process.env.E2E_FAKE_AI;
    else process.env.E2E_FAKE_AI = originalFlag;
    if (originalPublicFlag === undefined) delete process.env.NEXT_PUBLIC_E2E_FAKE_AI;
    else process.env.NEXT_PUBLIC_E2E_FAKE_AI = originalPublicFlag;
    if (originalVerify === undefined) delete process.env.M3_VERIFY;
    else process.env.M3_VERIFY = originalVerify;
    if (originalTestEmail === undefined) delete process.env.TEST_USER_EMAIL;
    else process.env.TEST_USER_EMAIL = originalTestEmail;
    if (originalPublicPosthogKey === undefined) delete process.env.NEXT_PUBLIC_POSTHOG_KEY;
    else process.env.NEXT_PUBLIC_POSTHOG_KEY = originalPublicPosthogKey;
  });

  it("forwards the event to posthog-js when traffic is not test traffic", async () => {
    const { capture } = await importFreshClientModule();

    capture("$pageview", { $current_url: "https://bucks.ai/dashboard" });

    expect(captureMock).toHaveBeenCalledWith("$pageview", { $current_url: "https://bucks.ai/dashboard" });
  });

  it("no-ops when NEXT_PUBLIC_E2E_FAKE_AI=true", async () => {
    process.env.NEXT_PUBLIC_E2E_FAKE_AI = "true";
    const { capture } = await importFreshClientModule();

    capture("$pageview", { $current_url: "https://bucks.ai/dashboard" });

    expect(captureMock).not.toHaveBeenCalled();
  });

  it("no-ops when the given email matches TEST_USER_EMAIL", async () => {
    process.env.TEST_USER_EMAIL = "qa@bucks.ai";
    const { capture } = await importFreshClientModule();

    capture("INTAKE_STARTED", {}, "qa@bucks.ai");

    expect(captureMock).not.toHaveBeenCalled();
  });

  it("no-ops when NEXT_PUBLIC_POSTHOG_KEY is unset", async () => {
    delete process.env.NEXT_PUBLIC_POSTHOG_KEY;
    const { capture } = await importFreshClientModule();

    capture("INTAKE_STARTED");

    expect(captureMock).not.toHaveBeenCalled();
  });

  it("re-enables capture and stamps verification_run when M3_VERIFY=true", async () => {
    process.env.NEXT_PUBLIC_E2E_FAKE_AI = "true";
    process.env.M3_VERIFY = "true";
    const { capture } = await importFreshClientModule();

    capture("INTAKE_STARTED", { foo: "bar" });

    expect(captureMock).toHaveBeenCalledWith("intake_started", { foo: "bar", verification_run: true });
  });
});
