// Zod schema for the POST /api/generate-blueprint request body.
// The body is the founder's startup idea intake, so it reuses startupIdeaSchema directly.

import type { z } from "zod";
import { startupIdeaSchema } from "@/lib/schemas/startup-idea";

export const generateBlueprintBodySchema = startupIdeaSchema;

export type GenerateBlueprintBody = z.infer<typeof generateBlueprintBodySchema>;
