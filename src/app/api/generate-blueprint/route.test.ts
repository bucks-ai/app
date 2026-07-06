import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const { requireUserMock, openaiCreateMock, openaiConstructorMock } = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  openaiCreateMock: vi.fn(),
  openaiConstructorMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("openai", () => ({
  default: class {
    chat = { completions: { create: openaiCreateMock } };
    constructor(...args: unknown[]) {
      openaiConstructorMock(...args);
    }
  },
}));

import { POST } from "./route";

function makeRequest(body: unknown) {
  return new NextRequest("http://localhost/api/generate-blueprint", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

const validIdea = {
  ideaName: "Test",
  oneLineIdea: "Test idea",
  primaryGoal: "Test goal",
  budget: "1000",
  timeline: "3 months",
};

const validBlueprint = {
  businessSummary: "A tool that helps small teams ship faster.",
  businessType: "B2B",
  targetCustomer: "Small engineering teams",
  painHypothesis: "Teams waste time on manual releases.",
  mvpScope: ["Automated release notes"],
  differentiation: ["Zero-config setup"],
  suggestedStack: ["Next.js", "Postgres"],
  requiredTools: [{ name: "GitHub", category: "Build", purpose: "Source control" }],
  requiredPermissions: [
    { title: "Repo access", reason: "To read commits", level: "Required" },
  ],
  goToMarketMotion: "Product-led growth",
  marketingPlan: {
    motion: "Content marketing",
    channels: ["Blog"],
    launchAssets: ["Landing page"],
    experiments: ["SEO test"],
  },
  salesPlan: {
    motion: "Self-serve",
    channels: ["Website"],
    enablement: ["Docs"],
    sequence: ["Trial", "Convert"],
  },
  analyticsPlan: {
    northStarMetric: "Weekly active teams",
    events: ["signup"],
    dashboards: ["Activation"],
    reviewCadence: ["Weekly"],
  },
  humanRequiredActions: [
    { title: "Register domain", reason: "Needed for launch", owner: "Founder" },
  ],
  nextAutonomousActions: [
    { title: "Deploy MVP", detail: "Ship the first release", phase: "Launch" },
  ],
  risks: ["Low initial adoption"],
  successMetrics: ["10 active teams in month 1"],
  killCriteria: ["No signups after 3 months"],
};

describe("POST /api/generate-blueprint", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    openaiCreateMock.mockReset();
    openaiConstructorMock.mockReset();
    process.env.OPENAI_API_KEY = "test-key";
  });

  it("returns the standard 401 envelope and never calls OpenAI when unauthenticated", async () => {
    const unauthorizedResponse = Response.json(
      { ok: false, error: "Authentication required.", code: "unauthenticated" },
      { status: 401 },
    );
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse });

    const response = await POST(
      makeRequest({
        ideaName: "Test",
        oneLineIdea: "Test idea",
        primaryGoal: "Test goal",
        budget: "1000",
        timeline: "3 months",
      }),
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(openaiConstructorMock).not.toHaveBeenCalled();
    expect(openaiCreateMock).not.toHaveBeenCalled();
  });

  it("proceeds to call OpenAI when authenticated and returns the blueprint on valid output", async () => {
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });
    openaiCreateMock.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify(validBlueprint) } }],
    });

    const response = await POST(makeRequest(validIdea));

    expect(response.status).toBe(200);
    expect(openaiCreateMock).toHaveBeenCalledTimes(1);
    const payload = await response.json();
    expect(payload.blueprint).toEqual(validBlueprint);
  });

  it("returns a 400 badRequest envelope with field issues and never calls OpenAI for a missing required field", async () => {
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });

    const response = await POST(
      makeRequest({
        oneLineIdea: "Test idea",
        primaryGoal: "Test goal",
        budget: "1000",
        timeline: "3 months",
      }),
    );

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.ok).toBe(false);
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.ideaName).toBeDefined();
    expect(openaiConstructorMock).not.toHaveBeenCalled();
    expect(openaiCreateMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope for an invalid businessTypeGuess enum value", async () => {
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });

    const response = await POST(
      makeRequest({
        ideaName: "Test",
        oneLineIdea: "Test idea",
        primaryGoal: "Test goal",
        budget: "1000",
        timeline: "3 months",
        businessTypeGuess: "Nonprofit",
      }),
    );

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("validation_error");
    expect(payload.issues.businessTypeGuess).toBeDefined();
    expect(openaiCreateMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope for a malformed JSON body", async () => {
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });

    const request = new NextRequest("http://localhost/api/generate-blueprint", {
      method: "POST",
      body: "{not valid json",
      headers: { "Content-Type": "application/json" },
    });

    const response = await POST(request);

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("invalid_json");
    expect(openaiCreateMock).not.toHaveBeenCalled();
  });

  it("returns a 502 AI_OUTPUT_INVALID envelope and logs the raw output for malformed AI output", async () => {
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });
    // Valid JSON, but missing most required blueprint fields and using a bad enum value.
    const malformedOutput = JSON.stringify({
      businessSummary: "ok",
      businessType: "Nonprofit",
    });
    openaiCreateMock.mockResolvedValue({
      choices: [{ message: { content: malformedOutput } }],
    });

    const response = await POST(makeRequest(validIdea));

    expect(response.status).toBe(502);
    const payload = await response.json();
    expect(payload).toEqual({
      ok: false,
      error: "The AI returned a blueprint that failed validation.",
      code: "AI_OUTPUT_INVALID",
    });
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      expect.stringContaining("AI output failed schema validation"),
      malformedOutput,
      expect.any(Array),
    );

    consoleErrorSpy.mockRestore();
  });

  it("returns a 500 parse_error envelope and never stores or renders truncated AI output", async () => {
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });
    // Simulates a response cut off mid-generation (e.g. hitting max_tokens): invalid JSON.
    const truncatedOutput = `{"businessSummary": "A tool that helps", "mvpScope": ["Feature A`;
    openaiCreateMock.mockResolvedValue({
      choices: [{ message: { content: truncatedOutput } }],
    });

    const response = await POST(makeRequest(validIdea));

    expect(response.status).toBe(500);
    const payload = await response.json();
    expect(payload.error).toBe("parse_error");
    expect(payload.blueprint).toBeUndefined();
  });
});
