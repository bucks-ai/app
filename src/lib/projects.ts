// Server-side data helpers for bucks.ai businesses.
// All functions are server-only — do not import from client components.
// Not yet wired into any UI; intended as the foundation for the dashboard branch.
//
// Results are cast to typed records since we use an untyped Supabase client
// (hand-rolled types rather than Supabase CLI-generated ones).

import { createSupabaseServerClient } from "@/lib/supabase/server";
import type {
  BusinessRecord,
  BusinessBlueprintRecord,
  HumanRequiredActionRecord,
  AgentActivityLogRecord,
  ToolPermissionRecord,
  NewBusinessInput,
  NewBusinessBlueprintInput,
  NewHumanRequiredActionInput,
  NewAgentActivityLogInput,
  NewToolPermissionInput,
} from "@/types/database";

// ---------------------------------------------------------------------------
// Result wrapper
// ---------------------------------------------------------------------------

type Result<T> =
  | { data: T; error: null }
  | { data: null; error: string };

function ok<T>(data: T): Result<T> {
  return { data, error: null };
}

function err<T>(message: string): Result<T> {
  return { data: null, error: message };
}

const NO_CLIENT =
  "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local.";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function getCurrentUser(): Promise<Result<{ id: string; email: string | null }>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) return err("Not authenticated.");

  return ok({ id: data.user.id, email: data.user.email ?? null });
}

// ---------------------------------------------------------------------------
// Businesses
// ---------------------------------------------------------------------------

export async function getUserBusinesses(): Promise<Result<BusinessRecord[]>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("businesses")
    .select("*")
    .order("created_at", { ascending: false });

  if (error) return err(error.message);
  return ok((data ?? []) as BusinessRecord[]);
}

export async function getBusinessById(id: string): Promise<Result<BusinessRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("businesses")
    .select("*")
    .eq("id", id)
    .single();

  if (error) return err(error.message);
  if (!data) return err(`Business ${id} not found.`);
  return ok(data as BusinessRecord);
}

export async function createBusiness(input: NewBusinessInput): Promise<Result<BusinessRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("businesses")
    .insert(input as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) return err(error.message);
  if (!data) return err("Failed to create business.");
  return ok(data as BusinessRecord);
}

// ---------------------------------------------------------------------------
// Blueprints
// ---------------------------------------------------------------------------

export async function getLatestBlueprintForBusiness(
  businessId: string
): Promise<Result<BusinessBlueprintRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("business_blueprints")
    .select("*")
    .eq("business_id", businessId)
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (error) return err(error.message);
  if (!data) return err(`No blueprint found for business ${businessId}.`);
  return ok(data as BusinessBlueprintRecord);
}

export async function saveBusinessBlueprint(
  input: NewBusinessBlueprintInput
): Promise<Result<BusinessBlueprintRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("business_blueprints")
    .insert(input as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) return err(error.message);
  if (!data) return err("Failed to save blueprint.");
  return ok(data as BusinessBlueprintRecord);
}

// ---------------------------------------------------------------------------
// Human Required Actions
// ---------------------------------------------------------------------------

export async function getHumanRequiredActions(
  businessId: string
): Promise<Result<HumanRequiredActionRecord[]>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("human_required_actions")
    .select("*")
    .eq("business_id", businessId)
    .order("created_at", { ascending: false });

  if (error) return err(error.message);
  return ok((data ?? []) as HumanRequiredActionRecord[]);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function normalizeRiskLevel(value: unknown, fallback = "medium") {
  const riskLevel = asString(value)?.toLowerCase();
  if (
    riskLevel === "low" ||
    riskLevel === "medium" ||
    riskLevel === "high" ||
    riskLevel === "critical"
  ) {
    return riskLevel;
  }

  return fallback;
}

function buildHumanActionInserts(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown>
): NewHumanRequiredActionInput[] {
  const inserts: NewHumanRequiredActionInput[] = [];
  const seenTitles = new Set<string>();

  function addAction(input: {
    title: string | null;
    description?: string | null;
    riskLevel?: string;
  }) {
    const title = input.title?.trim();
    if (!title) return;

    const key = title.toLowerCase();
    if (seenTitles.has(key)) return;
    seenTitles.add(key);

    inserts.push({
      business_id: businessId,
      user_id: userId,
      title,
      description: input.description ?? undefined,
      risk_level: input.riskLevel ?? "medium",
    });
  }

  const rawHumanActions = [
    ...asArray(blueprint.humanRequiredActions),
    ...asArray(blueprint.human_required_actions),
    ...asArray(blueprint.humanGates),
    ...asArray(blueprint.human_gates),
    ...asArray(blueprint.approvalGates),
    ...asArray(blueprint.approval_gates),
  ];

  for (const action of rawHumanActions) {
    if (typeof action === "string") {
      addAction({ title: action, riskLevel: "medium" });
      continue;
    }

    const record = asRecord(action);
    if (!record) continue;

    const reason =
      asString(record.reason) ??
      asString(record.description) ??
      asString(record.detail);

    addAction({
      title:
        asString(record.title) ??
        asString(record.action) ??
        asString(record.name) ??
        "Action required",
      description: reason,
      riskLevel: normalizeRiskLevel(record.risk_level ?? record.riskLevel),
    });
  }

  const rawPermissions = [
    ...asArray(blueprint.requiredPermissions),
    ...asArray(blueprint.required_permissions),
  ];

  for (const permission of rawPermissions) {
    if (typeof permission === "string") {
      addAction({
        title: `Approve ${permission}`,
        description: "Permission is required before autonomous execution.",
        riskLevel: "medium",
      });
      continue;
    }

    const record = asRecord(permission);
    if (!record) continue;

    const title = asString(record.title) ?? asString(record.name);
    const level = asString(record.level)?.toLowerCase();
    addAction({
      title: title ? `Approve ${title}` : "Approve required permission",
      description:
        asString(record.reason) ??
        asString(record.description) ??
        "Permission is required before autonomous execution.",
      riskLevel: level === "required" ? "high" : "medium",
    });
  }

  if (inserts.length === 0) {
    for (const risk of asArray(blueprint.risks).slice(0, 5)) {
      const title = asString(risk);
      addAction({
        title: title ? `Review risk: ${title}` : null,
        description: "Risk review is required before autonomous execution.",
        riskLevel: "high",
      });
    }
  }

  return inserts.slice(0, 12);
}

// Parses blueprint JSON for human-required actions and bulk-inserts them.
export async function createHumanRequiredActionsFromBlueprint(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown>
): Promise<Result<HumanRequiredActionRecord[]>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const inserts = buildHumanActionInserts(businessId, userId, blueprint);
  if (inserts.length === 0) return ok([]);

  const { data, error } = await supabase
    .from("human_required_actions")
    .insert(inserts as unknown as Record<string, unknown>[])
    .select();

  if (error) return err(error.message);
  return ok((data ?? []) as HumanRequiredActionRecord[]);
}

// ---------------------------------------------------------------------------
// Agent Activity Logs
// ---------------------------------------------------------------------------

export async function getAgentActivityLogs(
  businessId: string
): Promise<Result<AgentActivityLogRecord[]>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("agent_activity_logs")
    .select("*")
    .eq("business_id", businessId)
    .order("created_at", { ascending: false });

  if (error) return err(error.message);
  return ok((data ?? []) as AgentActivityLogRecord[]);
}

export async function createAgentActivityLog(
  input: NewAgentActivityLogInput
): Promise<Result<AgentActivityLogRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("agent_activity_logs")
    .insert(input as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) return err(error.message);
  if (!data) return err("Failed to create activity log.");
  return ok(data as AgentActivityLogRecord);
}

// ---------------------------------------------------------------------------
// Tool Permissions
// ---------------------------------------------------------------------------

export async function upsertToolPermission(
  input: NewToolPermissionInput
): Promise<Result<ToolPermissionRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("tool_permissions")
    .upsert(
      { ...(input as unknown as Record<string, unknown>), updated_at: new Date().toISOString() },
      { onConflict: "user_id,tool_id" }
    )
    .select()
    .single();

  if (error) return err(error.message);
  if (!data) return err("Failed to upsert tool permission.");
  return ok(data as ToolPermissionRecord);
}
