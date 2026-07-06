import { describe, expect, it } from "vitest";
import { z } from "zod";
import { badRequest, zodIssuesToFields } from "@/lib/api-error";

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
