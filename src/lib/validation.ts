// Customer Validation Node — server-side helpers.
//
// All public functions require an authenticated user and verify business
// ownership before reading or writing data.
//
// Safe to call when supabase/validation.sql has not yet been applied —
// returns error code "validation_schema_missing" in that case so the API
// layer can return a helpful message without crashing.
//
// This module is the data rail that future Customer Validation Node agents
// (Persona Agent, Hypothesis Agent, Lead Research Agent, Feedback Analysis
// Agent, Validation Score Agent) will call.

import { createSupabaseServerClient } from "@/lib/supabase/server";
import {
  getCurrentUser,
  getBusinessById,
  createAgentActivityLog,
} from "@/lib/projects";
import type {
  NewValidationPersonaInput,
  UpdateValidationPersonaInput,
  NewValidationHypothesisInput,
  UpdateValidationHypothesisInput,
  NewValidationLeadInput,
  UpdateValidationLeadInput,
  NewValidationFeedbackNoteInput,
  ValidationPersonaRecord,
  ValidationHypothesisRecord,
  ValidationLeadRecord,
  ValidationFeedbackNoteRecord,
  ValidationWorkspace,
  ValidationSummary,
  ValidationStatus,
  ValidationHypothesisType,
} from "@/types/validation";

// ---------------------------------------------------------------------------
// Result wrapper (matches pattern in src/lib/projects.ts)
// ---------------------------------------------------------------------------

type Result<T> =
  | { data: T; error: null; code?: undefined }
  | { data: null; error: string; code: string };

function ok<T>(data: T): Result<T> {
  return { data, error: null };
}

function err<T>(message: string, code = "unknown_error"): Result<T> {
  return { data: null, error: message, code };
}

const NO_CLIENT =
  "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local.";

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Detects a "relation does not exist" Postgres error (table not created yet). */
function isMissingTableError(e: { message?: string; code?: string }): boolean {
  return (
    e.code === "42P01" ||
    (typeof e.message === "string" &&
      e.message.includes("relation") &&
      e.message.includes("does not exist"))
  );
}

/** Strip undefined values so Supabase only updates supplied fields. */
function omitUndefined(obj: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined));
}

/** Build update payload by dropping id + business_id from the input object. */
function updatePayload(input: Record<string, unknown>): Record<string, unknown> {
  return omitUndefined(
    Object.fromEntries(
      Object.entries(input).filter(([k]) => k !== "id" && k !== "business_id")
    )
  );
}

async function getAuthenticatedUser() {
  const result = await getCurrentUser();
  if (result.error || !result.data) return null;
  return result.data;
}

async function verifyOwnership(businessId: string, userId: string): Promise<boolean> {
  const result = await getBusinessById(businessId);
  if (result.error || !result.data) return false;
  return result.data.user_id === userId;
}

function asStr(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

function asArr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

// ---------------------------------------------------------------------------
// Validation workspace status derivation
// ---------------------------------------------------------------------------

function deriveValidationStatus(
  personas: ValidationPersonaRecord[],
  hypotheses: ValidationHypothesisRecord[],
  leads: ValidationLeadRecord[],
  feedbackNotes: ValidationFeedbackNoteRecord[]
): ValidationStatus {
  if (personas.length === 0 && hypotheses.length === 0 && leads.length === 0) {
    return "not_started";
  }

  if (feedbackNotes.length > 0) {
    const interviewed = leads.filter((l) => l.status === "interviewed").length;
    const supported = hypotheses.filter((h) => h.status === "supported").length;
    if (supported > 0 && interviewed >= 5) return "validated";
    const rejected = hypotheses.filter((h) => h.status === "rejected").length;
    if (hypotheses.length > 0 && rejected > hypotheses.length / 2) return "needs_pivot";
    return "learning";
  }

  if (leads.some((l) => l.status === "scheduled")) return "interviews_scheduled";
  if (leads.some((l) => l.status === "contacted" || l.status === "replied")) {
    return "outreach_ready";
  }

  return "planned";
}

// ---------------------------------------------------------------------------
// getValidationWorkspace
// ---------------------------------------------------------------------------

export async function getValidationWorkspace(
  businessId: string
): Promise<Result<ValidationWorkspace>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(businessId, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const [personasRes, hypothesesRes, leadsRes, feedbackRes] = await Promise.all([
    supabase
      .from("validation_personas")
      .select("*")
      .eq("business_id", businessId)
      .order("created_at", { ascending: true }),
    supabase
      .from("validation_hypotheses")
      .select("*")
      .eq("business_id", businessId)
      .order("priority", { ascending: true })
      .order("created_at", { ascending: true }),
    supabase
      .from("validation_leads")
      .select("*")
      .eq("business_id", businessId)
      .order("priority", { ascending: true })
      .order("created_at", { ascending: true }),
    supabase
      .from("validation_feedback_notes")
      .select("*")
      .eq("business_id", businessId)
      .order("created_at", { ascending: false }),
  ]);

  for (const res of [personasRes, hypothesesRes, leadsRes, feedbackRes]) {
    if (res.error) {
      if (isMissingTableError(res.error as { message?: string; code?: string })) {
        return err(
          "Validation schema is not applied. Ask Satvik to run supabase/validation.sql in the Supabase SQL Editor.",
          "validation_schema_missing"
        );
      }
      return err(res.error.message, "query_error");
    }
  }

  const personas = (personasRes.data ?? []) as ValidationPersonaRecord[];
  const hypotheses = (hypothesesRes.data ?? []) as ValidationHypothesisRecord[];
  const leads = (leadsRes.data ?? []) as ValidationLeadRecord[];
  const feedbackNotes = (feedbackRes.data ?? []) as ValidationFeedbackNoteRecord[];

  const testedStatuses = new Set(["testing", "supported", "rejected", "inconclusive"]);

  const summary: ValidationSummary = {
    businessId,
    status: deriveValidationStatus(personas, hypotheses, leads, feedbackNotes),
    personaCount: personas.length,
    hypothesisCount: hypotheses.length,
    leadCount: leads.length,
    feedbackNoteCount: feedbackNotes.length,
    testedHypothesisCount: hypotheses.filter((h) => testedStatuses.has(h.status)).length,
    supportedHypothesisCount: hypotheses.filter((h) => h.status === "supported").length,
    interviewedLeadCount: leads.filter((l) => l.status === "interviewed").length,
    strongSignalCount: feedbackNotes.filter((n) => n.signal_strength === "strong").length,
    canSeed: personas.length === 0 && hypotheses.length === 0,
  };

  return ok({ summary, personas, hypotheses, leads, feedbackNotes });
}

// ---------------------------------------------------------------------------
// seedValidationWorkspaceFromBlueprint
// ---------------------------------------------------------------------------

export async function seedValidationWorkspaceFromBlueprint(businessId: string): Promise<
  Result<{ seeded: boolean; personas: number; hypotheses: number; leads: number }>
> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(businessId, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  // Fetch the latest blueprint — seeding works with or without one
  const { data: blueprints } = await supabase
    .from("business_blueprints")
    .select("blueprint")
    .eq("business_id", businessId)
    .order("created_at", { ascending: false })
    .limit(1);

  const blueprint =
    (blueprints?.[0]?.blueprint as Record<string, unknown> | null) ?? null;

  const personaInserts = buildPersonaSeeds(businessId, user.id, blueprint);
  const hypothesisInserts = buildHypothesisSeeds(businessId, user.id, blueprint);
  const leadInserts = buildLeadSeeds(businessId, user.id, blueprint);

  const personaRes = await supabase
    .from("validation_personas")
    .insert(personaInserts as unknown as Record<string, unknown>[])
    .select();

  if (personaRes.error) {
    if (isMissingTableError(personaRes.error as { message?: string; code?: string })) {
      return err(
        "Validation schema is not applied. Ask Satvik to run supabase/validation.sql.",
        "validation_schema_missing"
      );
    }
    return err(personaRes.error.message, "query_error");
  }

  const insertedPersonas = (personaRes.data ?? []) as ValidationPersonaRecord[];

  const hypothesisRes = await supabase
    .from("validation_hypotheses")
    .insert(hypothesisInserts as unknown as Record<string, unknown>[])
    .select();

  if (hypothesisRes.error) return err(hypothesisRes.error.message, "query_error");

  const leadRes = await supabase
    .from("validation_leads")
    .insert(leadInserts as unknown as Record<string, unknown>[])
    .select();

  if (leadRes.error) return err(leadRes.error.message, "query_error");

  void createAgentActivityLog({
    business_id: businessId,
    user_id: user.id,
    activity_type: "validation_workspace_seeded",
    message: `Customer Validation Node workspace seeded: ${insertedPersonas.length} personas, ${(hypothesisRes.data ?? []).length} hypotheses, ${(leadRes.data ?? []).length} leads.`,
    metadata: {
      personaCount: insertedPersonas.length,
      hypothesisCount: (hypothesisRes.data ?? []).length,
      leadCount: (leadRes.data ?? []).length,
      seededFromBlueprint: blueprint !== null,
    },
  });

  return ok({
    seeded: true,
    personas: insertedPersonas.length,
    hypotheses: (hypothesisRes.data ?? []).length,
    leads: (leadRes.data ?? []).length,
  });
}

// ---------------------------------------------------------------------------
// Seed builder helpers
// ---------------------------------------------------------------------------

function buildPersonaSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewValidationPersonaInput[] {
  const defaults: NewValidationPersonaInput[] = [
    {
      business_id: businessId,
      user_id: userId,
      name: "Early Adopter",
      segment: "Individual contributor or founder",
      description: "Hands-on operator who moves fast and values time savings over polish.",
      pain_points: ["Manual, repetitive processes slow them down", "Budget constraints limit tooling"],
      desired_outcomes: ["Validate the concept quickly", "Reduce operational overhead"],
      channels: ["Twitter / X", "Slack communities", "Direct outreach"],
      willingness_to_pay: "High — will pay if saves >2 hrs/week",
      priority: "high",
      status: "active",
    },
    {
      business_id: businessId,
      user_id: userId,
      name: "Decision Maker",
      segment: "VP, Director, or C-suite at mid-market company",
      description: "Budget owner who needs ROI justification and a risk-averse adoption path.",
      pain_points: ["Justifying ROI on new tools", "Team adoption friction and change management"],
      desired_outcomes: ["Scale without proportional headcount growth", "Demonstrate measurable value"],
      channels: ["LinkedIn", "Industry conferences", "Peer referrals"],
      willingness_to_pay: "Medium — needs clear ROI narrative",
      priority: "medium",
      status: "active",
    },
  ];

  if (!blueprint) return defaults;

  const rawPersonas = asArr(
    blueprint.targetPersonas ?? blueprint.target_personas ?? blueprint.personas
  );

  if (rawPersonas.length === 0) {
    const targetCustomer = asStr(blueprint.targetCustomer ?? blueprint.target_customer);
    if (targetCustomer) {
      defaults[0].name = targetCustomer;
      defaults[0].segment = targetCustomer;
    }
    return defaults;
  }

  return rawPersonas.slice(0, 3).map((p) => {
    const obj = (typeof p === "object" && p !== null ? p : {}) as Record<string, unknown>;
    return {
      business_id: businessId,
      user_id: userId,
      name: asStr(obj.name ?? obj.title ?? obj.persona) ?? "Target Customer",
      segment: asStr(obj.segment ?? obj.role ?? obj.jobTitle ?? obj.job_title),
      description: asStr(obj.description ?? obj.summary),
      pain_points: asArr(obj.painPoints ?? obj.pain_points).map(String).filter(Boolean),
      desired_outcomes: asArr(obj.goals ?? obj.objectives ?? obj.desiredOutcomes).map(String).filter(Boolean),
      channels: asArr(obj.channels).map(String).filter(Boolean),
      willingness_to_pay: asStr(obj.willingnessToPay ?? obj.willingness_to_pay),
      priority: "high" as const,
      status: "active",
    };
  });
}

function buildHypothesisSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewValidationHypothesisInput[] {
  const businessName =
    asStr(blueprint?.ideaName ?? blueprint?.idea_name ?? blueprint?.name) ?? "this business";
  const problem = asStr(blueprint?.problem ?? blueprint?.coreProblem ?? blueprint?.core_problem);
  const solution = asStr(blueprint?.solution ?? blueprint?.coreSolution ?? blueprint?.core_solution);
  const targetCustomer = asStr(blueprint?.targetCustomer ?? blueprint?.target_customer);

  const customerDesc = targetCustomer ?? "target customers";
  const problemDesc = problem ?? "the identified problem";
  const solutionDesc = solution ?? "the proposed solution";

  return [
    {
      business_id: businessId,
      user_id: userId,
      title: `${customerDesc} experience ${problemDesc} frequently enough to pay for a solution`,
      description: `If the pain is infrequent or low-severity, there is no viable market for ${businessName}.`,
      type: "customer" as ValidationHypothesisType,
      assumption: `${customerDesc} encounter this problem at least weekly and consider it a priority.`,
      success_criteria: "5+ interviewees describe the problem unprompted and rank it top-3.",
      status: "untested",
      priority: "high",
    },
    {
      business_id: businessId,
      user_id: userId,
      title: `${customerDesc} would switch to ${solutionDesc} given adequate awareness and onboarding`,
      description: "Switching cost is a common blocker even when pain is acknowledged.",
      type: "product" as ValidationHypothesisType,
      assumption: "The switching cost is low enough that customers would trial within 30 days.",
      success_criteria: "3+ interviewees say they would trial within 30 days given a free account.",
      status: "untested",
      priority: "high",
    },
    {
      business_id: businessId,
      user_id: userId,
      title: "Willingness-to-pay is sufficient to support the intended pricing model",
      description: "Validates the revenue hypothesis before building pricing infrastructure.",
      type: "revenue" as ValidationHypothesisType,
      assumption: `${customerDesc} will pay the target price tier without significant objection.`,
      success_criteria: "5+ interviewees confirm price is acceptable or lower than current spend.",
      status: "untested",
      priority: "medium",
    },
  ];
}

function buildLeadSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewValidationLeadInput[] {
  const targetCustomer =
    asStr(blueprint?.targetCustomer ?? blueprint?.target_customer) ?? "Target Buyer";

  const archetypes: { role: string; company: string; segment: string }[] = [
    { role: "Founder / early employee", company: "Startup (1–20 employees)", segment: "Early adopter" },
    { role: "Power user / practitioner", company: "SMB (20–100 employees)", segment: "SMB practitioner" },
    { role: "Decision maker / budget owner", company: "Mid-market (100–500 employees)", segment: "Mid-market buyer" },
    { role: "Enterprise champion", company: "Enterprise (500+ employees)", segment: "Enterprise evaluator" },
    { role: "Consultant / agency operator", company: "Agency or consultancy", segment: "Service provider" },
  ];

  return archetypes.map((a, i) => ({
    business_id: businessId,
    user_id: userId,
    name: `${targetCustomer} — Lead ${i + 1}`,
    role: a.role,
    company: a.company,
    segment: a.segment,
    source: "blueprint" as const,
    status: "identified" as const,
    notes: "Seed archetype. Replace name, company, and contact details with a real person.",
    priority: i < 2 ? ("high" as const) : ("medium" as const),
  }));
}

// ---------------------------------------------------------------------------
// CRUD — Personas
// ---------------------------------------------------------------------------

export async function createValidationPersona(
  input: NewValidationPersonaInput
): Promise<Result<ValidationPersonaRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("validation_personas")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err("Validation schema missing.", "validation_schema_missing");
    return err(error.message, "validation_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "validation_persona_created",
    message: `Persona "${input.name}" added to validation workspace.`,
    metadata: { personaName: input.name, priority: input.priority },
  });

  return ok(data as ValidationPersonaRecord);
}

export async function updateValidationPersona(
  input: UpdateValidationPersonaInput
): Promise<Result<ValidationPersonaRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("validation_personas")
    .update(updatePayload(input as unknown as Record<string, unknown>))
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err("Validation schema missing.", "validation_schema_missing");
    return err(error.message, "validation_update_failed");
  }

  return ok(data as ValidationPersonaRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Hypotheses
// ---------------------------------------------------------------------------

export async function createValidationHypothesis(
  input: NewValidationHypothesisInput
): Promise<Result<ValidationHypothesisRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("validation_hypotheses")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err("Validation schema missing.", "validation_schema_missing");
    return err(error.message, "validation_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "validation_hypothesis_created",
    message: `Hypothesis "${input.title}" added to validation workspace.`,
    metadata: { hypothesisTitle: input.title, type: input.type, priority: input.priority },
  });

  return ok(data as ValidationHypothesisRecord);
}

export async function updateValidationHypothesis(
  input: UpdateValidationHypothesisInput
): Promise<Result<ValidationHypothesisRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const payload = updatePayload(input as unknown as Record<string, unknown>);

  const { data, error } = await supabase
    .from("validation_hypotheses")
    .update(payload)
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err("Validation schema missing.", "validation_schema_missing");
    return err(error.message, "validation_update_failed");
  }

  if (input.status) {
    void createAgentActivityLog({
      business_id: input.business_id,
      user_id: user.id,
      activity_type: "validation_status_updated",
      message: `Hypothesis status updated to "${input.status}".`,
      metadata: { hypothesisId: input.id, newStatus: input.status },
    });
  }

  return ok(data as ValidationHypothesisRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Leads
// ---------------------------------------------------------------------------

export async function createValidationLead(
  input: NewValidationLeadInput
): Promise<Result<ValidationLeadRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("validation_leads")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err("Validation schema missing.", "validation_schema_missing");
    return err(error.message, "validation_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "validation_lead_created",
    message: `Lead "${input.name}" added to validation workspace.`,
    metadata: { leadName: input.name, source: input.source, priority: input.priority },
  });

  return ok(data as ValidationLeadRecord);
}

export async function updateValidationLead(
  input: UpdateValidationLeadInput
): Promise<Result<ValidationLeadRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const payload = updatePayload(input as unknown as Record<string, unknown>);

  const { data, error } = await supabase
    .from("validation_leads")
    .update(payload)
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err("Validation schema missing.", "validation_schema_missing");
    return err(error.message, "validation_update_failed");
  }

  if (input.status) {
    void createAgentActivityLog({
      business_id: input.business_id,
      user_id: user.id,
      activity_type: "validation_status_updated",
      message: `Lead "${data.name}" status updated to "${input.status}".`,
      metadata: { leadId: input.id, newStatus: input.status },
    });
  }

  return ok(data as ValidationLeadRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Feedback Notes
// ---------------------------------------------------------------------------

export async function createValidationFeedbackNote(
  input: NewValidationFeedbackNoteInput
): Promise<Result<ValidationFeedbackNoteRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("validation_feedback_notes")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err("Validation schema missing.", "validation_schema_missing");
    return err(error.message, "validation_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "validation_feedback_added",
    message: "Customer feedback note recorded.",
    metadata: {
      signalStrength: input.signal_strength ?? "unrated",
      hasLead: Boolean(input.lead_id),
      hasHypothesis: Boolean(input.hypothesis_id),
    },
  });

  return ok(data as ValidationFeedbackNoteRecord);
}

// ---------------------------------------------------------------------------
// getValidationSummary (lightweight — workspace summary only)
// ---------------------------------------------------------------------------

export async function getValidationSummary(
  businessId: string
): Promise<Result<ValidationSummary>> {
  const result = await getValidationWorkspace(businessId);
  if (result.error || !result.data) {
    return err(result.error ?? "Failed to load workspace.", result.code ?? "unknown_error");
  }
  return ok(result.data.summary);
}
