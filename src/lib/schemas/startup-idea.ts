// Zod schema for the founder-intake shape shared by /api/generate-blueprint
// and the startupIdea field of /api/businesses/save-blueprint.
// Mirrors src/types/startup.ts StartupIdea, keeping the same 5 fields required
// (ideaName, oneLineIdea, primaryGoal, budget, timeline) as the routes previously
// enforced by hand.

import { z } from "zod";

export const businessTypeGuessSchema = z.enum([
  "B2B",
  "B2C",
  "Prosumer",
  "Creator Tool",
  "Agency Tool",
  "Unsure",
]);

export const autonomyPreferenceSchema = z.enum([
  "Recommend only",
  "Ask before major actions",
  "Execute within limits",
  "Maximum autonomy",
]);

function requiredField(field: string) {
  return z.string().trim().min(1, `${field} is required.`);
}

export const startupIdeaSchema = z.object({
  ideaName: requiredField("ideaName"),
  oneLineIdea: requiredField("oneLineIdea"),
  ideaDescription: z.string().optional(),
  targetCustomer: z.string().optional(),
  businessTypeGuess: businessTypeGuessSchema.optional(),
  primaryGoal: requiredField("primaryGoal"),
  successMetric: z.string().optional(),
  budget: requiredField("budget"),
  timeline: requiredField("timeline"),
  autonomyPreference: autonomyPreferenceSchema.optional(),
  spendingLimit: z.string().optional(),
  hardConstraints: z.string().optional(),
  humanOnlyActions: z.string().optional(),
  forbiddenActions: z.string().optional(),
  preferredTools: z.string().optional(),
});

export type StartupIdeaBody = z.infer<typeof startupIdeaSchema>;
