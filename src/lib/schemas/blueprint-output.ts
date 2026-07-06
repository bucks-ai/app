// Zod schema for the BusinessBlueprint object the AI model returns from
// POST /api/generate-blueprint. Mirrors src/types/startup.ts BusinessBlueprint.
// This validates the model's raw output itself (stricter than
// src/lib/schemas/save-blueprint.ts, which passes through unknown fields when
// re-saving an already-generated blueprint).

import { z } from "zod";
import { businessTypeGuessSchema } from "@/lib/schemas/startup-idea";

const nonEmptyString = z.string().trim().min(1);

const suggestedToolSchema = z.object({
  name: nonEmptyString,
  category: z.enum(["Build", "Growth", "Analytics", "Operations"]),
  purpose: nonEmptyString,
});

const requiredPermissionSchema = z.object({
  title: nonEmptyString,
  reason: nonEmptyString,
  level: z.enum(["Required", "Recommended"]),
});

const humanRequiredActionSchema = z.object({
  title: nonEmptyString,
  reason: nonEmptyString,
  owner: nonEmptyString,
});

const nextAutonomousActionSchema = z.object({
  title: nonEmptyString,
  detail: nonEmptyString,
  phase: nonEmptyString,
});

const marketingPlanSchema = z.object({
  motion: nonEmptyString,
  channels: z.array(nonEmptyString),
  launchAssets: z.array(nonEmptyString),
  experiments: z.array(nonEmptyString),
});

const salesPlanSchema = z.object({
  motion: nonEmptyString,
  channels: z.array(nonEmptyString),
  enablement: z.array(nonEmptyString),
  sequence: z.array(nonEmptyString),
});

const analyticsPlanSchema = z.object({
  northStarMetric: nonEmptyString,
  events: z.array(nonEmptyString),
  dashboards: z.array(nonEmptyString),
  reviewCadence: z.array(nonEmptyString),
});

export const businessBlueprintOutputSchema = z.object({
  businessSummary: nonEmptyString,
  businessType: businessTypeGuessSchema,
  targetCustomer: nonEmptyString,
  painHypothesis: nonEmptyString,
  mvpScope: z.array(nonEmptyString),
  differentiation: z.array(nonEmptyString),
  suggestedStack: z.array(nonEmptyString),
  requiredTools: z.array(suggestedToolSchema),
  requiredPermissions: z.array(requiredPermissionSchema),
  goToMarketMotion: nonEmptyString,
  marketingPlan: marketingPlanSchema,
  salesPlan: salesPlanSchema,
  analyticsPlan: analyticsPlanSchema,
  humanRequiredActions: z.array(humanRequiredActionSchema),
  nextAutonomousActions: z.array(nextAutonomousActionSchema),
  risks: z.array(nonEmptyString),
  successMetrics: z.array(nonEmptyString),
  killCriteria: z.array(nonEmptyString),
});

export type BusinessBlueprintOutput = z.infer<typeof businessBlueprintOutputSchema>;
