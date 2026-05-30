// Customer Validation Node — TypeScript types.
// These mirror the schema in supabase/validation.sql.
//
// This module is the type foundation for the Customer Validation Node.
// Future agents (Persona Agent, Hypothesis Agent, Lead Research Agent,
// Feedback Analysis Agent, Validation Score Agent) will import from here.

// ---------------------------------------------------------------------------
// Enum-like string union types
// ---------------------------------------------------------------------------

/** Overall status of the validation workspace for a business. */
export type ValidationStatus =
  | "not_started"
  | "planned"
  | "outreach_ready"
  | "interviews_scheduled"
  | "learning"
  | "validated"
  | "invalidated"
  | "needs_pivot";

/** Status of a single customer interview lead. */
export type ValidationLeadStatus =
  | "identified"
  | "contacted"
  | "replied"
  | "scheduled"
  | "interviewed"
  | "not_interested";

/** Status of a single validation hypothesis. */
export type ValidationHypothesisStatus =
  | "untested"
  | "testing"
  | "supported"
  | "rejected"
  | "inconclusive";

/** Relative priority across all validation entities. */
export type ValidationPriority = "high" | "medium" | "low";

/** How a customer lead was sourced. */
export type ValidationSource =
  | "manual"
  | "blueprint"
  | "linkedin"
  | "twitter"
  | "email"
  | "referral"
  | "other";

/** Qualitative signal strength from a feedback note. */
export type ValidationSignalStrength = "weak" | "medium" | "strong";

/** Category of a hypothesis — used by future Hypothesis Agent. */
export type ValidationHypothesisType =
  | "customer"
  | "market"
  | "product"
  | "revenue"
  | "other";

// ---------------------------------------------------------------------------
// Row types — shape of a row returned by SELECT
// ---------------------------------------------------------------------------

/** A target customer archetype to validate against. */
export interface ValidationPersonaRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** Display name for this persona segment. */
  name: string;
  /** Market segment label (e.g. "SMB founder", "enterprise ops manager"). */
  segment: string | null;
  /** Free-text description of who this persona is. */
  description: string | null;
  /** Core pain points this persona experiences. */
  pain_points: string[] | null;
  /** Outcomes this persona is trying to achieve. */
  desired_outcomes: string[] | null;
  /** Channels this persona uses (e.g. LinkedIn, email, Slack communities). */
  channels: string[] | null;
  /** Qualitative willingness-to-pay signal (e.g. "$50-200/mo", "high"). */
  willingness_to_pay: string | null;
  priority: ValidationPriority;
  /** "active" | "archived" — soft-delete pattern for pruned personas. */
  status: string;
  created_at: string;
  updated_at: string;
}

/** A testable belief about the market, customer, or product. */
export interface ValidationHypothesisRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** Short descriptive title (e.g. "Target users pay for time savings"). */
  title: string;
  /** Why we believe this hypothesis is true. */
  description: string | null;
  /** Category: customer | market | product | revenue | other. */
  type: ValidationHypothesisType | null;
  /** The core assumption being tested. */
  assumption: string | null;
  /** What evidence would confirm or reject this hypothesis. */
  success_criteria: string | null;
  status: ValidationHypothesisStatus;
  /** 0–100 confidence score — updated by Validation Score Agent in future. */
  confidence: number | null;
  priority: ValidationPriority;
  created_at: string;
  updated_at: string;
}

/** A potential customer to contact for discovery interviews. */
export interface ValidationLeadRecord {
  id: string;
  business_id: string;
  user_id: string;
  name: string;
  company: string | null;
  role: string | null;
  /** Customer segment this lead belongs to. */
  segment: string | null;
  source: ValidationSource;
  /** LinkedIn URL, website, or other profile link. */
  contact_url: string | null;
  email: string | null;
  status: ValidationLeadStatus;
  notes: string | null;
  priority: ValidationPriority;
  created_at: string;
  updated_at: string;
}

/** A structured note from a customer conversation. */
export interface ValidationFeedbackNoteRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** Lead this note was captured from (optional). */
  lead_id: string | null;
  /** Hypothesis this note relates to (optional). */
  hypothesis_id: string | null;
  /** What the customer said / key takeaway. */
  summary: string;
  /** Specific pain-point signal observed. */
  pain_signal: string | null;
  /** Willingness-to-pay signal ("yes at $X", "unsure", etc.). */
  willingness_to_pay_signal: string | null;
  /** Objections raised by the customer. */
  objections: string[] | null;
  /** Direct quotes captured from the conversation. */
  quotes: string[] | null;
  /** Agreed next step with or about this lead. */
  next_step: string | null;
  signal_strength: ValidationSignalStrength | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Aggregate / workspace types
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
  interviewedLeadCount: number;
  strongSignalCount: number;
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
  segment?: string | null;
  description?: string | null;
  pain_points?: string[] | null;
  desired_outcomes?: string[] | null;
  channels?: string[] | null;
  willingness_to_pay?: string | null;
  priority?: ValidationPriority;
  status?: string;
}

export interface NewValidationHypothesisInput {
  business_id: string;
  user_id: string;
  title: string;
  description?: string | null;
  type?: ValidationHypothesisType | null;
  assumption?: string | null;
  success_criteria?: string | null;
  status?: ValidationHypothesisStatus;
  confidence?: number | null;
  priority?: ValidationPriority;
}

export interface NewValidationLeadInput {
  business_id: string;
  user_id: string;
  name: string;
  company?: string | null;
  role?: string | null;
  segment?: string | null;
  source?: ValidationSource;
  contact_url?: string | null;
  email?: string | null;
  status?: ValidationLeadStatus;
  notes?: string | null;
  priority?: ValidationPriority;
}

export interface NewValidationFeedbackNoteInput {
  business_id: string;
  user_id: string;
  lead_id?: string | null;
  hypothesis_id?: string | null;
  summary: string;
  pain_signal?: string | null;
  willingness_to_pay_signal?: string | null;
  objections?: string[] | null;
  quotes?: string[] | null;
  next_step?: string | null;
  signal_strength?: ValidationSignalStrength | null;
}

// ---------------------------------------------------------------------------
// Input types — update
// ---------------------------------------------------------------------------

export interface UpdateValidationPersonaInput {
  id: string;
  business_id: string;
  name?: string;
  segment?: string | null;
  description?: string | null;
  pain_points?: string[] | null;
  desired_outcomes?: string[] | null;
  channels?: string[] | null;
  willingness_to_pay?: string | null;
  priority?: ValidationPriority;
  status?: string;
}

export interface UpdateValidationHypothesisInput {
  id: string;
  business_id: string;
  title?: string;
  description?: string | null;
  type?: ValidationHypothesisType | null;
  assumption?: string | null;
  success_criteria?: string | null;
  status?: ValidationHypothesisStatus;
  confidence?: number | null;
  priority?: ValidationPriority;
}

export interface UpdateValidationLeadInput {
  id: string;
  business_id: string;
  name?: string;
  company?: string | null;
  role?: string | null;
  segment?: string | null;
  source?: ValidationSource;
  contact_url?: string | null;
  email?: string | null;
  status?: ValidationLeadStatus;
  notes?: string | null;
  priority?: ValidationPriority;
}

export interface UpdateValidationFeedbackNoteInput {
  id: string;
  business_id: string;
  summary?: string;
  pain_signal?: string | null;
  willingness_to_pay_signal?: string | null;
  objections?: string[] | null;
  quotes?: string[] | null;
  next_step?: string | null;
  signal_strength?: ValidationSignalStrength | null;
  hypothesis_id?: string | null;
}
