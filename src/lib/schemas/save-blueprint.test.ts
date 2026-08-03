import { describe, expect, it } from "vitest";
import { businessBlueprintSchema, saveBlueprintBodySchema } from "@/lib/schemas/save-blueprint";

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

describe("businessBlueprintSchema", () => {
  it("accepts a blueprint with only businessSummary", () => {
    expect(businessBlueprintSchema.safeParse({ businessSummary: "A summary" }).success).toBe(true);
  });

  it("passes through unknown blueprint fields untouched", () => {
    const result = businessBlueprintSchema.safeParse({
      businessSummary: "A summary",
      mvpScope: ["Ship v1"],
      humanRequiredActions: [{ title: "Sign contract", reason: "Legal", owner: "Founder" }],
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.mvpScope).toEqual(["Ship v1"]);
    }
  });

  it("rejects a blueprint missing businessSummary", () => {
    expect(businessBlueprintSchema.safeParse({}).success).toBe(false);
  });

  it("rejects an invalid businessType enum value", () => {
    const result = businessBlueprintSchema.safeParse({
      businessSummary: "A summary",
      businessType: "Nonprofit",
    });
    expect(result.success).toBe(false);
  });
});

describe("saveBlueprintBodySchema", () => {
  it("accepts a valid body", () => {
    expect(saveBlueprintBodySchema.safeParse(validBody).success).toBe(true);
  });

  it("rejects a body missing startupIdea", () => {
    const rest: Record<string, unknown> = { ...validBody };
    delete rest.startupIdea;
    const result = saveBlueprintBodySchema.safeParse(rest);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(
        result.error.issues.some((issue) => issue.path.join(".").startsWith("startupIdea")),
      ).toBe(true);
    }
  });

  it("rejects a body missing blueprint", () => {
    const rest: Record<string, unknown> = { ...validBody };
    delete rest.blueprint;
    const result = saveBlueprintBodySchema.safeParse(rest);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(
        result.error.issues.some((issue) => issue.path.join(".").startsWith("blueprint")),
      ).toBe(true);
    }
  });

  it("rejects a startupIdea missing required fields", () => {
    const result = saveBlueprintBodySchema.safeParse({
      ...validBody,
      startupIdea: { ideaName: "Test" },
    });
    expect(result.success).toBe(false);
  });
});
