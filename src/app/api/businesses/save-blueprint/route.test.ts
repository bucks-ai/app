import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const {
  requireUserMock,
  hasSupabaseEnvMock,
  createBusinessMock,
  saveBusinessBlueprintMock,
  createHumanRequiredActionsFromBlueprintMock,
  createAgentActivityLogMock,
  seedToolPermissionsForBusinessMock,
} = vi.hoisted(() => ({
  requireUserMock: vi.fn(),
  hasSupabaseEnvMock: vi.fn(),
  createBusinessMock: vi.fn(),
  saveBusinessBlueprintMock: vi.fn(),
  createHumanRequiredActionsFromBlueprintMock: vi.fn(),
  createAgentActivityLogMock: vi.fn(),
  seedToolPermissionsForBusinessMock: vi.fn(),
}));

vi.mock("@/lib/api-auth", () => ({
  requireUser: requireUserMock,
}));

vi.mock("@/lib/supabase/env", () => ({
  hasSupabaseEnv: hasSupabaseEnvMock,
}));

vi.mock("@/lib/projects", () => ({
  createBusiness: createBusinessMock,
  saveBusinessBlueprint: saveBusinessBlueprintMock,
  createHumanRequiredActionsFromBlueprint: createHumanRequiredActionsFromBlueprintMock,
  createAgentActivityLog: createAgentActivityLogMock,
}));

vi.mock("@/lib/tool-permissions", () => ({
  seedToolPermissionsForBusiness: seedToolPermissionsForBusinessMock,
  createToolPermissionActivityLog: vi.fn(),
}));

import { POST } from "./route";

function makeRequest(body: unknown) {
  return new NextRequest("http://localhost/api/businesses/save-blueprint", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

const validBody = {
  startupIdea: {
    ideaName: "Test",
    oneLineIdea: "Test idea",
    primaryGoal: "Test goal",
    budget: "1000",
    timeline: "3 months",
  },
  blueprint: { businessSummary: "A summary" },
};

describe("POST /api/businesses/save-blueprint", () => {
  beforeEach(() => {
    requireUserMock.mockReset();
    hasSupabaseEnvMock.mockReset();
    createBusinessMock.mockReset();
    saveBusinessBlueprintMock.mockReset();
    createHumanRequiredActionsFromBlueprintMock.mockReset();
    createAgentActivityLogMock.mockReset();
    seedToolPermissionsForBusinessMock.mockReset();
    hasSupabaseEnvMock.mockReturnValue(true);
  });

  it("returns the standard 401 envelope and never writes to the database when unauthenticated", async () => {
    const unauthorizedResponse = Response.json(
      { ok: false, error: "Authentication required.", code: "unauthenticated" },
      { status: 401 },
    );
    requireUserMock.mockResolvedValue({ user: null, response: unauthorizedResponse });

    const response = await POST(makeRequest(validBody));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
    expect(createBusinessMock).not.toHaveBeenCalled();
    expect(saveBusinessBlueprintMock).not.toHaveBeenCalled();
    expect(createHumanRequiredActionsFromBlueprintMock).not.toHaveBeenCalled();
    expect(createAgentActivityLogMock).not.toHaveBeenCalled();
    expect(seedToolPermissionsForBusinessMock).not.toHaveBeenCalled();
  });

  it("proceeds to write to the database when authenticated", async () => {
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });
    createBusinessMock.mockResolvedValue({ data: { id: "biz-1" }, error: null });
    saveBusinessBlueprintMock.mockResolvedValue({ data: { id: "bp-1" }, error: null });
    createHumanRequiredActionsFromBlueprintMock.mockResolvedValue({ data: [], error: null });
    createAgentActivityLogMock.mockResolvedValue({ data: { id: "log-1" }, error: null });
    seedToolPermissionsForBusinessMock.mockResolvedValue({
      data: { seeded: 0, skipped: 0 },
      error: null,
    });

    const response = await POST(makeRequest(validBody));

    expect(response.status).toBe(200);
    expect(createBusinessMock).toHaveBeenCalledTimes(1);
  });

  it("returns a 400 badRequest envelope and never writes to the database when startupIdea is missing required fields", async () => {
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });

    const response = await POST(
      makeRequest({
        ...validBody,
        startupIdea: { ideaName: "Test" },
      }),
    );

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.ok).toBe(false);
    expect(payload.code).toBe("validation_error");
    expect(payload.issues).toBeDefined();
    expect(createBusinessMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope and never writes to the database when blueprint is missing businessSummary", async () => {
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });

    const response = await POST(
      makeRequest({
        ...validBody,
        blueprint: {},
      }),
    );

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("validation_error");
    expect(payload.issues["blueprint.businessSummary"]).toBeDefined();
    expect(createBusinessMock).not.toHaveBeenCalled();
  });

  it("returns a 400 badRequest envelope for a malformed JSON body", async () => {
    requireUserMock.mockResolvedValue({
      user: { id: "user-1", email: "a@example.com" },
      response: null,
    });
    hasSupabaseEnvMock.mockReturnValue(true);

    const request = new NextRequest("http://localhost/api/businesses/save-blueprint", {
      method: "POST",
      body: "{not valid json",
      headers: { "Content-Type": "application/json" },
    });

    const response = await POST(request);

    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.code).toBe("invalid_json");
    expect(createBusinessMock).not.toHaveBeenCalled();
  });
});
