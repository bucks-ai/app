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

// Parses blueprint JSON for human-required actions and bulk-inserts them.
export async function createHumanRequiredActionsFromBlueprint(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown>
): Promise<Result<HumanRequiredActionRecord[]>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const rawActions =
    (blueprint.humanRequiredActions as unknown[]) ??
    (blueprint.human_required_actions as unknown[]) ??
    [];

  if (!Array.isArray(rawActions) || rawActions.length === 0) return ok([]);

  const inserts: NewHumanRequiredActionInput[] = rawActions
    .filter((a): a is Record<string, unknown> => typeof a === "object" && a !== null)
    .map((a) => ({
      business_id: businessId,
      user_id: userId,
      title: String(a.title ?? a.action ?? "Action required"),
      description: a.description ? String(a.description) : undefined,
      risk_level: a.risk_level ? String(a.risk_level) : undefined,
    }));

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
