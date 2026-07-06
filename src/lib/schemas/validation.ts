// Zod schemas for the customer-validation workspace mutating routes under
// src/app/api/businesses/[id]/validation/**.
// Mirrors the *Input types in src/types/validation.ts. Update schemas are
// derived from the create schema (all fields optional) plus a required id.

import { z } from "zod";

export const validationPrioritySchema = z.enum(["high", "medium", "low"]);

const nullableString = z.string().nullable().optional();
const nullableStringArray = z.array(z.string()).nullable().optional();

function requiredField(field: string) {
  return z.string().trim().min(1, `${field} is required.`);
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/validation
// ---------------------------------------------------------------------------

export const seedValidationBodySchema = z.object({
  action: z.literal("seed"),
});

export type SeedValidationBody = z.infer<typeof seedValidationBodySchema>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/validation/personas
// ---------------------------------------------------------------------------

export const createValidationPersonaBodySchema = z.object({
  name: requiredField("name"),
  segment: nullableString,
  description: nullableString,
  pain_points: nullableStringArray,
  desired_outcomes: nullableStringArray,
  channels: nullableStringArray,
  willingness_to_pay: nullableString,
  priority: validationPrioritySchema.optional(),
  status: z.string().optional(),
});

export const updateValidationPersonaBodySchema = createValidationPersonaBodySchema
  .partial()
  .extend({ id: requiredField("id (persona uuid)") });

export type CreateValidationPersonaBody = z.infer<typeof createValidationPersonaBodySchema>;
export type UpdateValidationPersonaBody = z.infer<typeof updateValidationPersonaBodySchema>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/validation/hypotheses
// ---------------------------------------------------------------------------

export const validationHypothesisStatusSchema = z.enum([
  "untested",
  "testing",
  "supported",
  "rejected",
  "inconclusive",
]);

export const validationHypothesisTypeSchema = z.enum([
  "customer",
  "market",
  "product",
  "revenue",
  "other",
]);

export const createValidationHypothesisBodySchema = z.object({
  title: requiredField("title"),
  description: nullableString,
  type: validationHypothesisTypeSchema.nullable().optional(),
  assumption: nullableString,
  success_criteria: nullableString,
  status: validationHypothesisStatusSchema.optional(),
  confidence: z.number().min(0).max(100).nullable().optional(),
  priority: validationPrioritySchema.optional(),
});

export const updateValidationHypothesisBodySchema = createValidationHypothesisBodySchema
  .partial()
  .extend({ id: requiredField("id (hypothesis uuid)") });

export type CreateValidationHypothesisBody = z.infer<typeof createValidationHypothesisBodySchema>;
export type UpdateValidationHypothesisBody = z.infer<typeof updateValidationHypothesisBodySchema>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/validation/leads
// ---------------------------------------------------------------------------

export const validationLeadStatusSchema = z.enum([
  "identified",
  "contacted",
  "replied",
  "scheduled",
  "interviewed",
  "not_interested",
]);

export const validationSourceSchema = z.enum([
  "manual",
  "blueprint",
  "linkedin",
  "twitter",
  "email",
  "referral",
  "other",
]);

export const createValidationLeadBodySchema = z.object({
  name: requiredField("name"),
  company: nullableString,
  role: nullableString,
  segment: nullableString,
  source: validationSourceSchema.optional(),
  contact_url: nullableString,
  email: nullableString,
  status: validationLeadStatusSchema.optional(),
  notes: nullableString,
  priority: validationPrioritySchema.optional(),
});

export const updateValidationLeadBodySchema = createValidationLeadBodySchema
  .partial()
  .extend({ id: requiredField("id (lead uuid)") });

export type CreateValidationLeadBody = z.infer<typeof createValidationLeadBodySchema>;
export type UpdateValidationLeadBody = z.infer<typeof updateValidationLeadBodySchema>;

// ---------------------------------------------------------------------------
// /api/businesses/[id]/validation/feedback (create only)
// ---------------------------------------------------------------------------

export const validationSignalStrengthSchema = z.enum(["weak", "medium", "strong"]);

export const createValidationFeedbackNoteBodySchema = z.object({
  summary: requiredField("summary"),
  lead_id: nullableString,
  hypothesis_id: nullableString,
  pain_signal: nullableString,
  willingness_to_pay_signal: nullableString,
  objections: nullableStringArray,
  quotes: nullableStringArray,
  next_step: nullableString,
  signal_strength: validationSignalStrengthSchema.nullable().optional(),
});

export type CreateValidationFeedbackNoteBody = z.infer<
  typeof createValidationFeedbackNoteBodySchema
>;
