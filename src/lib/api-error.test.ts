import { beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import {
  aiOutputInvalid,
  apiError,
  badRequest,
  notFound,
  serverError,
  unauthorized,
  zodIssuesToFields,
} from "@/lib/api-error";

vi.mock("@sentry/nextjs", () => ({
  captureException: vi.fn(),
}));

import * as Sentry from "@sentry/nextjs";

describe("apiError", () => {
  it("returns the standard envelope with the given status", async () => {
    const response = apiError("Access denied.", "forbidden", 403);
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Access denied.",
      code: "forbidden",
    });
  });

  it("spreads extra fields into the envelope when given", async () => {
    const response = apiError("Scaffold failed.", "scaffold_failed", 500, {
      detail: { failedFile: "package.json" },
    });
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Scaffold failed.",
      code: "scaffold_failed",
      detail: { failedFile: "package.json" },
    });
  });
});

describe("unauthorized", () => {
  it("returns a 401 envelope with a default message", async () => {
    const response = unauthorized();
    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Authentication required.",
      code: "unauthenticated",
    });
  });
});

describe("notFound", () => {
  it("returns a 404 envelope with a default code", async () => {
    const response = notFound("Business not found.");
    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Business not found.",
      code: "not_found",
    });
  });

  it("supports a custom code", async () => {
    const response = notFound("Business not found.", "business_not_found");
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Business not found.",
      code: "business_not_found",
    });
  });
});

describe("aiOutputInvalid", () => {
  it("returns a 502 AI_OUTPUT_INVALID envelope", async () => {
    const response = aiOutputInvalid("The AI returned a blueprint that failed validation.");
    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "The AI returned a blueprint that failed validation.",
      code: "AI_OUTPUT_INVALID",
    });
  });
});

describe("badRequest", () => {
  it("returns a 400 envelope without issues when none are given", async () => {
    const response = badRequest("Request body must be valid JSON.", "invalid_json");
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Request body must be valid JSON.",
      code: "invalid_json",
    });
  });

  it("includes field-level issues in the envelope when given", async () => {
    const response = badRequest("Request body failed validation.", "validation_error", {
      ideaName: ["ideaName is required."],
    });
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Request body failed validation.",
      code: "validation_error",
      issues: { ideaName: ["ideaName is required."] },
    });
  });
});

describe("serverError", () => {
  const originalDsn = process.env.SENTRY_DSN;

  beforeEach(() => {
    vi.clearAllMocks();
    process.env.SENTRY_DSN = originalDsn;
  });

  it("returns a 500 envelope", async () => {
    const response = serverError(new Error("boom"));
    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Something went wrong. Please try again.",
      code: "internal_error",
    });
  });

  it("supports a custom message", async () => {
    const response = serverError(new Error("boom"), "Custom failure message.");
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Custom failure message.",
      code: "internal_error",
    });
  });

  it("reports the exception to Sentry when a DSN is configured", () => {
    process.env.SENTRY_DSN = "https://examplePublicKey@o0.ingest.sentry.io/0";
    const error = new Error("boom");

    serverError(error);

    expect(Sentry.captureException).toHaveBeenCalledTimes(1);
    expect(Sentry.captureException).toHaveBeenCalledWith(error);
  });

  it("does not call Sentry when no DSN is configured", () => {
    delete process.env.SENTRY_DSN;
    const error = new Error("boom");

    serverError(error);

    expect(Sentry.captureException).not.toHaveBeenCalled();
  });
});

describe("zodIssuesToFields", () => {
  it("groups issues by dotted field path", () => {
    const schema = z.object({
      ideaName: z.string().min(1),
      nested: z.object({ value: z.string() }),
    });
    const result = schema.safeParse({ ideaName: "", nested: {} });
    expect(result.success).toBe(false);
    if (result.success) return;

    const fields = zodIssuesToFields(result.error);
    expect(Object.keys(fields).sort()).toEqual(["ideaName", "nested.value"]);
    expect(fields.ideaName.length).toBeGreaterThan(0);
  });

  it("uses _body as the key for root-level issues", () => {
    const schema = z.string();
    const result = schema.safeParse(123);
    expect(result.success).toBe(false);
    if (result.success) return;

    const fields = zodIssuesToFields(result.error);
    expect(Object.keys(fields)).toEqual(["_body"]);
  });
});
