// Zod schema for the POST /api/businesses/save-blueprint request body.

import { z } from "zod";
import { businessTypeGuessSchema, startupIdeaSchema } from "@/lib/schemas/startup-idea";

// The generated blueprint's shape varies by model output beyond businessSummary/
// businessType (see the defensive multi-key reads in src/lib/projects.ts), so
// only those two fields are validated and the rest pass through unchanged.
export const businessBlueprintSchema = z
  .object({
    businessSummary: z.string(),
    businessType: businessTypeGuessSchema.optional(),
  })
  .passthrough();

export const saveBlueprintBodySchema = z.object({
  startupIdea: startupIdeaSchema,
  blueprint: businessBlueprintSchema,
});

export type SaveBlueprintBody = z.infer<typeof saveBlueprintBodySchema>;
