import { describe, expect, it } from "vitest";
import { startupIdeaSchema } from "@/lib/schemas/startup-idea";

const validIdea = {
  ideaName: "Test",
  oneLineIdea: "Test idea",
  primaryGoal: "Test goal",
  budget: "1000",
  timeline: "3 months",
};

describe("startupIdeaSchema", () => {
  it("accepts a payload with only the required fields", () => {
    const result = startupIdeaSchema.safeParse(validIdea);
    expect(result.success).toBe(true);
  });

  it("accepts a payload with all optional fields populated", () => {
    const result = startupIdeaSchema.safeParse({
      ...validIdea,
      ideaDescription: "A description",
      targetCustomer: "Freelancers",
      businessTypeGuess: "B2C",
      successMetric: "Signups",
      autonomyPreference: "Ask before major actions",
      spendingLimit: "500",
      hardConstraints: "None",
      humanOnlyActions: "None",
      forbiddenActions: "None",
      preferredTools: "Stripe",
    });
    expect(result.success).toBe(true);
  });

  it.each(["ideaName", "oneLineIdea", "primaryGoal", "budget", "timeline"])(
    "rejects a payload missing required field %s",
    (field) => {
      const rest: Record<string, string> = { ...validIdea };
      delete rest[field];
      const result = startupIdeaSchema.safeParse(rest);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues.some((issue) => issue.path.join(".") === field)).toBe(true);
      }
    },
  );

  it("rejects a payload with a blank required field", () => {
    const result = startupIdeaSchema.safeParse({ ...validIdea, ideaName: "   " });
    expect(result.success).toBe(false);
  });

  it("rejects an invalid businessTypeGuess enum value", () => {
    const result = startupIdeaSchema.safeParse({ ...validIdea, businessTypeGuess: "Nonprofit" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((issue) => issue.path.join(".") === "businessTypeGuess")).toBe(
        true,
      );
    }
  });

  it("rejects a non-object payload", () => {
    const result = startupIdeaSchema.safeParse("not an object");
    expect(result.success).toBe(false);
  });
});
