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

  it("proceeds to call OpenAI when authenticated", async () => {
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });
    openaiCreateMock.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify({ businessSummary: "ok" }) } }],
    });

    const response = await POST(
      makeRequest({
        ideaName: "Test",
        oneLineIdea: "Test idea",
        primaryGoal: "Test goal",
        budget: "1000",
        timeline: "3 months",
      }),
    );

    expect(response.status).toBe(200);
    expect(openaiCreateMock).toHaveBeenCalledTimes(1);
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
});
