// TypeScript types for the Customer Validation Module.
// These mirror the schema in supabase/validation.sql.

// ---------------------------------------------------------------------------
// Enum-like string union types
// ---------------------------------------------------------------------------

export type ValidationStatus =
  | "not_started"
  | "planned"
  | "outreach_ready"
  | "interviews_scheduled"
  | "learning"
  | "validated"
  | "invalidated"
  | "needs_pivot";

export type ValidationLeadStatus =
  | "identified"
  | "contacted"
  | "replied"
  | "scheduled"
  | "interviewed"
  | "not_interested";

export type ValidationHypothesisStatus =
  | "untested"
  | "testing"
  | "supported"
  | "rejected"
  | "inconclusive";

export type ValidationPriority = "high" | "medium" | "low";

export type ValidationSource =
  | "manual"
  | "blueprint"
  | "linkedin"
  | "twitter"
  | "email"
  | "referral"
  | "other";

export type ValidationSentiment = "positive" | "negative" | "neutral";

// ---------------------------------------------------------------------------
// Row types — shape of a row returned by SELECT
// ---------------------------------------------------------------------------

export interface ValidationPersonaRecord {
  id: string;
  business_id: string;
  user_id: string;
  name: string;
  role: string | null;
  company_type: string | null;
  pain_points: string[] | null;
  goals: string[] | null;
  notes: string | null;
  priority: ValidationPriority;
  created_at: string;
  updated_at: string;
}

export interface ValidationHypothesisRecord {
  id: string;
  business_id: string;
  user_id: string;
  statement: string;
  rationale: string | null;
  status: ValidationHypothesisStatus;
  evidence: string | null;
  created_at: string;
  updated_at: string;
}

export interface ValidationLeadRecord {
  id: string;
  business_id: string;
  user_id: string;
  name: string;
  company: string | null;
  role: string | null;
  contact_info: string | null;
  source: ValidationSource;
  status: ValidationLeadStatus;
  persona_id: string | null;
  notes: string | null;
  outreach_script: string | null;
  created_at: string;
  updated_at: string;
}

export interface ValidationFeedbackNoteRecord {
  id: string;
  business_id: string;
  user_id: string;
  lead_id: string | null;
  persona_id: string | null;
  hypothesis_id: string | null;
  note: string;
  sentiment: ValidationSentiment | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Aggregate types
// ---------------------------------------------------------------------------

export interface ValidationSummary {
  businessId: string;
  status: ValidationStatus;
  personaCount: number;
  hypothesisCount: number;
  leadCount: number;
  feedbackNoteCount: number;
  testedHypothesisCount: number;
  supportedHypothesisCount: number;
  rejectedHypothesisCount: number;
  contactedLeadCount: number;
  interviewedLeadCount: number;
  canSeed: boolean;
}

export interface ValidationWorkspace {
  summary: ValidationSummary;
  personas: ValidationPersonaRecord[];
  hypotheses: ValidationHypothesisRecord[];
  leads: ValidationLeadRecord[];
  feedbackNotes: ValidationFeedbackNoteRecord[];
}

// ---------------------------------------------------------------------------
// Input types — create
// ---------------------------------------------------------------------------

export interface NewValidationPersonaInput {
  business_id: string;
  user_id: string;
  name: string;
  role?: string | null;
  company_type?: string | null;
  pain_points?: string[] | null;
  goals?: string[] | null;
  notes?: string | null;
  priority?: ValidationPriority;
}

export interface NewValidationHypothesisInput {
  business_id: string;
  user_id: string;
  statement: string;
  rationale?: string | null;
  status?: ValidationHypothesisStatus;
}

export interface NewValidationLeadInput {
  business_id: string;
  user_id: string;
  name: string;
  company?: string | null;
  role?: string | null;
  contact_info?: string | null;
  source?: ValidationSource;
  status?: ValidationLeadStatus;
  persona_id?: string | null;
  notes?: string | null;
  outreach_script?: string | null;
}

export interface NewValidationFeedbackNoteInput {
  business_id: string;
  user_id: string;
  lead_id?: string | null;
  persona_id?: string | null;
  hypothesis_id?: string | null;
  note: string;
  sentiment?: ValidationSentiment | null;
}

// ---------------------------------------------------------------------------
// Input types — update
// ---------------------------------------------------------------------------

export interface UpdateValidationPersonaInput {
  id: string;
  business_id: string;
  name?: string;
  role?: string | null;
  company_type?: string | null;
  pain_points?: string[] | null;
  goals?: string[] | null;
  notes?: string | null;
  priority?: ValidationPriority;
}

export interface UpdateValidationHypothesisInput {
  id: string;
  business_id: string;
  statement?: string;
  rationale?: string | null;
  status?: ValidationHypothesisStatus;
  evidence?: string | null;
}

export interface UpdateValidationLeadInput {
  id: string;
  business_id: string;
  name?: string;
  company?: string | null;
  role?: string | null;
  contact_info?: string | null;
  source?: ValidationSource;
  status?: ValidationLeadStatus;
  persona_id?: string | null;
  notes?: string | null;
  outreach_script?: string | null;
}

export interface UpdateValidationFeedbackNoteInput {
  id: string;
  business_id: string;
  note?: string;
  sentiment?: ValidationSentiment | null;
  hypothesis_id?: string | null;
}
