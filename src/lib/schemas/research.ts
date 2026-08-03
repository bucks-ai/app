// Zod schemas for the research workspace mutating routes under
// src/app/api/businesses/[id]/research/**.
// Mirrors the *Input types in src/types/research.ts. Update schemas are
// derived from the create schema (all fields optional) plus a required id.

import { z } from "zod";

export const researchConfidenceSchema = z.enum([
  "assumption",
  "weak_signal",
  "medium_signal",
  "strong_signal",
  "validated",
  "invalidated",
]);

export const researchPrioritySchema = z.enum(["high", "medium", "low"]);

const nullableString = z.string().nullable().optional();
const nullableStringArray = z.array(z.string()).nullable().optional();
const nullableScore = z.number().min(0).max(10).nullable().optional();

function requiredField(field: string) {
  return z.string().trim().min(1, `${field} is required.`);
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/research
// ---------------------------------------------------------------------------

export const generateResearchBodySchema = z.object({
  action: z.literal("generate"),
});

export type GenerateResearchBody = z.infer<typeof generateResearchBodySchema>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/research/segments
// ---------------------------------------------------------------------------

export const createResearchSegmentBodySchema = z.object({
  name: requiredField("name"),
  description: nullableString,
  pain_level: nullableScore,
  ability_to_pay: nullableScore,
  reachability: nullableScore,
  market_size_guess: nullableString,
  channels: nullableStringArray,
  evidence_summary: nullableString,
  confidence: researchConfidenceSchema.nullable().optional(),
  priority: researchPrioritySchema.optional(),
});

export const updateResearchSegmentBodySchema = createResearchSegmentBodySchema
  .partial()
  .extend({ id: requiredField("id (segment uuid)") });

export type CreateResearchSegmentBody = z.infer<typeof createResearchSegmentBodySchema>;
export type UpdateResearchSegmentBody = z.infer<typeof updateResearchSegmentBodySchema>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/research/buyer-budgets
// ---------------------------------------------------------------------------

export const createResearchBuyerBudgetBodySchema = z.object({
  buyer: requiredField("buyer"),
  budget_owner: nullableString,
  existing_spend: nullableString,
  willingness_to_pay: nullableString,
  value_driver: nullableString,
  pricing_signal: nullableString,
  confidence: researchConfidenceSchema.nullable().optional(),
  priority: researchPrioritySchema.optional(),
});

export const updateResearchBuyerBudgetBodySchema = createResearchBuyerBudgetBodySchema
  .partial()
  .extend({ id: requiredField("id (record uuid)") });

export type CreateResearchBuyerBudgetBody = z.infer<typeof createResearchBuyerBudgetBodySchema>;
export type UpdateResearchBuyerBudgetBody = z.infer<typeof updateResearchBuyerBudgetBodySchema>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/research/competitors
// ---------------------------------------------------------------------------

export const researchCompetitorCategorySchema = z.enum([
  "direct",
  "indirect",
  "substitute",
  "emerging",
]);

export const createResearchCompetitorBodySchema = z.object({
  name: requiredField("name"),
  url: nullableString,
  category: researchCompetitorCategorySchema.nullable().optional(),
  positioning: nullableString,
  pricing_summary: nullableString,
  strengths: nullableStringArray,
  weaknesses: nullableStringArray,
  wedge_opportunity: nullableString,
  confidence: researchConfidenceSchema.nullable().optional(),
  priority: researchPrioritySchema.optional(),
});

export const updateResearchCompetitorBodySchema = createResearchCompetitorBodySchema
  .partial()
  .extend({ id: requiredField("id (competitor uuid)") });

export type CreateResearchCompetitorBody = z.infer<typeof createResearchCompetitorBodySchema>;
export type UpdateResearchCompetitorBody = z.infer<typeof updateResearchCompetitorBodySchema>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/research/distribution
// ---------------------------------------------------------------------------

export const createResearchDistributionChannelBodySchema = z.object({
  channel: requiredField("channel"),
  description: nullableString,
  speed_score: nullableScore,
  cost_score: nullableScore,
  difficulty_score: nullableScore,
  reasoning: nullableString,
  confidence: researchConfidenceSchema.nullable().optional(),
  priority: researchPrioritySchema.optional(),
});

export const updateResearchDistributionChannelBodySchema =
  createResearchDistributionChannelBodySchema
    .partial()
    .extend({ id: requiredField("id (channel uuid)") });

export type CreateResearchDistributionChannelBody = z.infer<
  typeof createResearchDistributionChannelBodySchema
>;
export type UpdateResearchDistributionChannelBody = z.infer<
  typeof updateResearchDistributionChannelBodySchema
>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/research/risks
// ---------------------------------------------------------------------------

export const researchRiskSeveritySchema = z.enum(["critical", "high", "medium", "low"]);

export const createResearchRiskBodySchema = z.object({
  title: requiredField("title"),
  description: nullableString,
  severity: researchRiskSeveritySchema.nullable().optional(),
  mitigation: nullableString,
  confidence: researchConfidenceSchema.nullable().optional(),
  priority: researchPrioritySchema.optional(),
});

export const updateResearchRiskBodySchema = createResearchRiskBodySchema
  .partial()
  .extend({ id: requiredField("id (risk uuid)") });

export type CreateResearchRiskBody = z.infer<typeof createResearchRiskBodySchema>;
export type UpdateResearchRiskBody = z.infer<typeof updateResearchRiskBodySchema>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/research/hypotheses
// ---------------------------------------------------------------------------

export const createResearchHypothesisBodySchema = z.object({
  title: requiredField("title"),
  description: nullableString,
  test_method: nullableString,
  success_criteria: nullableString,
  confidence: researchConfidenceSchema.nullable().optional(),
  priority: researchPrioritySchema.optional(),
});

export const updateResearchHypothesisBodySchema = createResearchHypothesisBodySchema
  .partial()
  .extend({ id: requiredField("id (hypothesis uuid)") });

export type CreateResearchHypothesisBody = z.infer<typeof createResearchHypothesisBodySchema>;
export type UpdateResearchHypothesisBody = z.infer<typeof updateResearchHypothesisBodySchema>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/research/monetization
// ---------------------------------------------------------------------------

export const createResearchMonetizationModelBodySchema = z.object({
  model: requiredField("model"),
  buyer: nullableString,
  price_assumption: nullableString,
  value_metric: nullableString,
  reasoning: nullableString,
  confidence: researchConfidenceSchema.nullable().optional(),
  priority: researchPrioritySchema.optional(),
});

export const updateResearchMonetizationModelBodySchema =
  createResearchMonetizationModelBodySchema
    .partial()
    .extend({ id: requiredField("id (model uuid)") });

export type CreateResearchMonetizationModelBody = z.infer<
  typeof createResearchMonetizationModelBodySchema
>;
export type UpdateResearchMonetizationModelBody = z.infer<
  typeof updateResearchMonetizationModelBodySchema
>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/research/evidence (create only — append-only records)
// ---------------------------------------------------------------------------

export const researchEvidenceTypeSchema = z.enum([
  "data_point",
  "quote",
  "case_study",
  "trend",
  "competitor_signal",
  "customer_signal",
  "market_report",
]);

export const createResearchEvidenceBodySchema = z.object({
  claim: requiredField("claim"),
  source: nullableString,
  source_url: nullableString,
  evidence_type: researchEvidenceTypeSchema.nullable().optional(),
  confidence: researchConfidenceSchema.nullable().optional(),
  notes: nullableString,
});

export type CreateResearchEvidenceBody = z.infer<typeof createResearchEvidenceBodySchema>;
