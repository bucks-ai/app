// Server-side helpers for the Customer Validation Module.
// All functions require an authenticated user and verify business ownership.
// Safe to call when supabase/validation.sql has not yet been applied —
// returns error code "validation_schema_missing" in that case.

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
} from "@/types/validation";

// ---------------------------------------------------------------------------
// Result wrapper
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

function isMissingTableError(e: { message?: string; code?: string }): boolean {
  return (
    e.code === "42P01" ||
    (typeof e.message === "string" &&
      e.message.includes("relation") &&
      e.message.includes("does not exist"))
  );
}

function omitUndefined(obj: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined));
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
      .order("created_at", { ascending: true }),
    supabase
      .from("validation_leads")
      .select("*")
      .eq("business_id", businessId)
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
    rejectedHypothesisCount: hypotheses.filter((h) => h.status === "rejected").length,
    contactedLeadCount: leads.filter((l) => l.status !== "identified").length,
    interviewedLeadCount: leads.filter((l) => l.status === "interviewed").length,
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
  const firstPersonaId = insertedPersonas[0]?.id ?? null;

  const leadsWithPersona = leadInserts.map((lead) => ({
    ...lead,
    persona_id: firstPersonaId,
  }));

  const hypothesisRes = await supabase
    .from("validation_hypotheses")
    .insert(hypothesisInserts as unknown as Record<string, unknown>[])
    .select();

  if (hypothesisRes.error) return err(hypothesisRes.error.message, "query_error");

  const leadRes = await supabase
    .from("validation_leads")
    .insert(leadsWithPersona as unknown as Record<string, unknown>[])
    .select();

  if (leadRes.error) return err(leadRes.error.message, "query_error");

  void createAgentActivityLog({
    business_id: businessId,
    user_id: user.id,
    activity_type: "validation_workspace_seeded",
    message: `Validation workspace seeded with ${insertedPersonas.length} personas, ${(hypothesisRes.data ?? []).length} hypotheses, and ${(leadRes.data ?? []).length} leads.`,
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
      role: "Individual contributor or founder",
      company_type: "Early-stage startup or SMB",
      pain_points: ["Manual processes slowing them down", "Limited budget for tooling"],
      goals: ["Validate the concept quickly", "Reduce operational overhead"],
      priority: "high",
    },
    {
      business_id: businessId,
      user_id: userId,
      name: "Decision Maker",
      role: "VP, Director, or C-suite",
      company_type: "Mid-market company (50-500 employees)",
      pain_points: ["Justifying ROI on new tools", "Team adoption friction"],
      goals: ["Scale efficiently", "Demonstrate measurable value to stakeholders"],
      priority: "medium",
    },
  ];

  if (!blueprint) return defaults;

  const rawPersonas = asArr(
    blueprint.targetPersonas ?? blueprint.target_personas ?? blueprint.personas
  );

  if (rawPersonas.length === 0) {
    const targetCustomer = asStr(blueprint.targetCustomer ?? blueprint.target_customer);
    if (targetCustomer) defaults[0].name = targetCustomer;
    return defaults;
  }

  return rawPersonas.slice(0, 3).map((p) => {
    const obj = (typeof p === "object" && p !== null ? p : {}) as Record<string, unknown>;
    return {
      business_id: businessId,
      user_id: userId,
      name: asStr(obj.name ?? obj.title ?? obj.persona) ?? "Target Customer",
      role: asStr(obj.role ?? obj.jobTitle ?? obj.job_title),
      company_type: asStr(obj.companyType ?? obj.company_type ?? obj.company),
      pain_points: asArr(obj.painPoints ?? obj.pain_points)
        .map(String)
        .filter(Boolean),
      goals: asArr(obj.goals ?? obj.objectives)
        .map(String)
        .filter(Boolean),
      priority: "high" as const,
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
  const solution = asStr(
    blueprint?.solution ?? blueprint?.coreSolution ?? blueprint?.core_solution
  );
  const targetCustomer = asStr(blueprint?.targetCustomer ?? blueprint?.target_customer);

  const customerDesc = targetCustomer ?? "Target customers";
  const problemDesc = problem ?? "the identified problem";
  const solutionDesc = solution ?? "the proposed solution";

  return [
    {
      business_id: businessId,
      user_id: userId,
      statement: `${customerDesc} experience ${problemDesc} frequently enough to pay for a solution.`,
      rationale: `If the pain is not frequent or severe, there is no viable market for ${businessName}.`,
      status: "untested",
    },
    {
      business_id: businessId,
      user_id: userId,
      statement: `${customerDesc} would switch to ${solutionDesc} given adequate awareness and onboarding.`,
      rationale:
        "Switching cost is a common blocker even when the pain is clearly acknowledged.",
      status: "untested",
    },
    {
      business_id: businessId,
      user_id: userId,
      statement: `The willingness-to-pay for ${solutionDesc} is sufficient to support the intended pricing model.`,
      rationale:
        "Validating price sensitivity early prevents over-engineering a feature set customers cannot justify purchasing.",
      status: "untested",
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

  const archetypes = [
    {
      name: `${targetCustomer} — Lead 1`,
      role: "Early adopter",
      company: "Startup (1-20 employees)",
      notes: "Seed archetype. Replace with a real contact.",
    },
    {
      name: `${targetCustomer} — Lead 2`,
      role: "Power user",
      company: "SMB (20-100 employees)",
      notes: "Seed archetype. Replace with a real contact.",
    },
    {
      name: `${targetCustomer} — Lead 3`,
      role: "Decision maker",
      company: "Mid-market (100-500 employees)",
      notes: "Seed archetype. Replace with a real contact.",
    },
    {
      name: `${targetCustomer} — Lead 4`,
      role: "Budget owner",
      company: "Enterprise (500+ employees)",
      notes: "Seed archetype. Replace with a real contact.",
    },
    {
      name: `${targetCustomer} — Lead 5`,
      role: "End user",
      company: "Agency or consultancy",
      notes: "Seed archetype. Replace with a real contact.",
    },
  ];

  return archetypes.map((a) => ({
    business_id: businessId,
    user_id: userId,
    name: a.name,
    role: a.role,
    company: a.company,
    source: "blueprint" as const,
    status: "identified" as const,
    notes: a.notes,
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
    return err(error.message, "query_error");
  }

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

  const updateFields = omitUndefined(
    Object.fromEntries(
      Object.entries(input as unknown as Record<string, unknown>).filter(
        ([k]) => k !== "id" && k !== "business_id"
      )
    )
  );

  const { data, error } = await supabase
    .from("validation_personas")
    .update({ ...updateFields, updated_at: new Date().toISOString() })
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err("Validation schema missing.", "validation_schema_missing");
    return err(error.message, "query_error");
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
    return err(error.message, "query_error");
  }

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

  const updateFields = omitUndefined(
    Object.fromEntries(
      Object.entries(input as unknown as Record<string, unknown>).filter(
        ([k]) => k !== "id" && k !== "business_id"
      )
    )
  );

  const { data, error } = await supabase
    .from("validation_hypotheses")
    .update({ ...updateFields, updated_at: new Date().toISOString() })
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err("Validation schema missing.", "validation_schema_missing");
    return err(error.message, "query_error");
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
    return err(error.message, "query_error");
  }

  if (input.status && input.status !== "identified") {
    void createAgentActivityLog({
      business_id: input.business_id,
      user_id: user.id,
      activity_type: "validation_lead_contacted",
      message: `First outreach lead added: ${input.name}.`,
      metadata: { leadName: input.name, status: input.status, source: input.source },
    });
  }

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

  const updateFields = omitUndefined(
    Object.fromEntries(
      Object.entries(input as unknown as Record<string, unknown>).filter(
        ([k]) => k !== "id" && k !== "business_id"
      )
    )
  );

  const { data, error } = await supabase
    .from("validation_leads")
    .update({ ...updateFields, updated_at: new Date().toISOString() })
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err("Validation schema missing.", "validation_schema_missing");
    return err(error.message, "query_error");
  }

  if (input.status && input.status !== "identified") {
    void createAgentActivityLog({
      business_id: input.business_id,
      user_id: user.id,
      activity_type: "validation_status_updated",
      message: `Lead status updated to "${input.status}".`,
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
    return err(error.message, "query_error");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "validation_feedback_added",
    message: "Validation feedback note recorded.",
    metadata: {
      sentiment: input.sentiment ?? "neutral",
      hasLead: Boolean(input.lead_id),
      hasHypothesis: Boolean(input.hypothesis_id),
    },
  });

  return ok(data as ValidationFeedbackNoteRecord);
}

// ---------------------------------------------------------------------------
// Summary
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
