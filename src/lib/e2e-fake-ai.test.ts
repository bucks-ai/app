import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { businessBlueprintOutputSchema } from "@/lib/schemas/blueprint-output";
import type { GenerateBlueprintBody } from "@/lib/schemas/generate-blueprint";
import { buildFakeBlueprint, isFakeAiEnabled } from "@/lib/e2e-fake-ai";

const minimalBody: GenerateBlueprintBody = {
  ideaName: "Test",
  oneLineIdea: "Test idea",
  primaryGoal: "Test goal",
  budget: "1000",
  timeline: "3 months",
};

const fullBody: GenerateBlueprintBody = {
  ideaName: "Launch Copilot",
  oneLineIdea: "AI copilot for solo founders shipping their first product",
  ideaDescription: "Turns a rough idea into a launch-ready plan.",
  targetCustomer: "Solo technical founders",
  businessTypeGuess: "B2B",
  primaryGoal: "Validate demand for the copilot",
  successMetric: "10 paying teams in 60 days",
  budget: "5000",
  timeline: "6 weeks",
  autonomyPreference: "Execute within limits",
  spendingLimit: "500",
  hardConstraints: "No paid ads",
  humanOnlyActions: "Sign vendor contracts",
  forbiddenActions: "No cold outbound",
  preferredTools: "Vercel, PostHog",
};

describe("isFakeAiEnabled", () => {
  const originalFlag = process.env.E2E_FAKE_AI;
  const originalNodeEnv = process.env.NODE_ENV;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    if (originalFlag === undefined) delete process.env.E2E_FAKE_AI;
    else process.env.E2E_FAKE_AI = originalFlag;

    vi.stubEnv("NODE_ENV", originalNodeEnv ?? "test");
  });

  it("is false when E2E_FAKE_AI is unset", () => {
    delete process.env.E2E_FAKE_AI;
    vi.stubEnv("NODE_ENV", "development");

    expect(isFakeAiEnabled()).toBe(false);
  });

  it("is false when E2E_FAKE_AI is not exactly \"true\"", () => {
    process.env.E2E_FAKE_AI = "1";
    vi.stubEnv("NODE_ENV", "development");

    expect(isFakeAiEnabled()).toBe(false);
  });

  it("is true when E2E_FAKE_AI=true and NODE_ENV is not production", () => {
    process.env.E2E_FAKE_AI = "true";
    vi.stubEnv("NODE_ENV", "development");

    expect(isFakeAiEnabled()).toBe(true);
  });

  it("ignores the flag and logs a warning when NODE_ENV=production", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    process.env.E2E_FAKE_AI = "true";
    vi.stubEnv("NODE_ENV", "production");

    expect(isFakeAiEnabled()).toBe(false);
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("NODE_ENV=production"),
    );
  });
});

describe("buildFakeBlueprint", () => {
  it("produces a fixture that validates against businessBlueprintOutputSchema for a minimal body", () => {
    const fixture = buildFakeBlueprint(minimalBody);
    const result = businessBlueprintOutputSchema.safeParse(fixture);

    expect(result.success).toBe(true);
  });

  it("produces a fixture that validates against businessBlueprintOutputSchema for a fully-populated body", () => {
    const fixture = buildFakeBlueprint(fullBody);
    const result = businessBlueprintOutputSchema.safeParse(fixture);

    expect(result.success).toBe(true);
  });

  it("is deterministic for the same input", () => {
    expect(buildFakeBlueprint(fullBody)).toEqual(buildFakeBlueprint(fullBody));
  });
});
