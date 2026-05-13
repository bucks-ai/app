// Server-side helpers for the Tool Permission Setup Flow.
// All functions are server-only — do not import from client components.

import { createSupabaseServerClient } from "@/lib/supabase/server";
import { toolRegistry } from "@/lib/tool-registry";
import type { ToolPermissionRecord, NewToolPermissionInput } from "@/types/database";
import type {
  ToolPermissionStatus,
  ToolSetupStatus,
  ToolPermissionView,
  ToolPermissionUpdateInput,
  ToolPermissionSeedResult,
} from "@/types/tool-permissions";
import { ACTION_STATUS_MAP as actionStatusMap } from "@/types/tool-permissions";
import type { ToolRegistryItem } from "@/types/tools";

// ---------------------------------------------------------------------------
// Result wrapper (consistent with projects.ts)
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
// Seed status mapping
// Translates tool registry static data → initial permission state.
// ---------------------------------------------------------------------------

const TOOL_SEED_OVERRIDES: Record<
  string,
  { status: ToolPermissionStatus; setup_status: ToolSetupStatus }
> = {
  github: { status: "approval_requested", setup_status: "awaiting_founder_approval" },
  vercel: { status: "approval_requested", setup_status: "awaiting_founder_approval" },
  supabase: { status: "connected_demo", setup_status: "connected_demo" },
  stripe: { status: "human_required", setup_status: "awaiting_identity_or_payment" },
  posthog: { status: "approval_requested", setup_status: "awaiting_founder_approval" },
  "gmail-google-workspace": { status: "human_required", setup_status: "awaiting_human_legal_step" },
  airtable: { status: "approval_requested", setup_status: "awaiting_founder_approval" },
  resend: { status: "approval_requested", setup_status: "awaiting_founder_approval" },
  openai: { status: "approval_requested", setup_status: "awaiting_identity_or_payment" },
  anthropic: { status: "approval_requested", setup_status: "awaiting_identity_or_payment" },
  firecrawl: { status: "approval_requested", setup_status: "awaiting_founder_approval" },
  sentry: { status: "approval_requested", setup_status: "awaiting_founder_approval" },
  cloudflare: { status: "human_required", setup_status: "awaiting_human_legal_step" },
  clerk: { status: "approval_requested", setup_status: "awaiting_founder_approval" },
  "e2b-docker-sandbox": { status: "approval_requested", setup_status: "awaiting_founder_approval" },
};

function getInitialStatusForTool(tool: ToolRegistryItem): {
  status: ToolPermissionStatus;
  setup_status: ToolSetupStatus;
} {
  const override = TOOL_SEED_OVERRIDES[tool.id];
  if (override) return override;

  // Fallback: anything with identity/payment requirements stays human_required
  if (tool.requiresIdentityVerification || (tool.requiresPaymentSetup && tool.riskLevel === "Critical")) {
    return { status: "human_required", setup_status: "awaiting_identity_or_payment" };
  }

  if (tool.requiresTermsAcceptance && tool.riskLevel === "High") {
    return { status: "human_required", setup_status: "awaiting_human_legal_step" };
  }

  if (tool.status === "Blocked") {
    return { status: "blocked", setup_status: "blocked" };
  }

  return { status: "approval_requested", setup_status: "awaiting_founder_approval" };
}

function normalizeRiskLevel(raw: string): string {
  const lower = raw.toLowerCase();
  if (lower === "low" || lower === "medium" || lower === "high" || lower === "critical") {
    return lower;
  }
  return "medium";
}

// ---------------------------------------------------------------------------
// Ownership guard
// Returns null if the user owns the business, or an error string.
// ---------------------------------------------------------------------------

async function verifyBusinessOwnership(
  businessId: string,
  userId: string
): Promise<string | null> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return NO_CLIENT;

  const { data, error } = await supabase
    .from("businesses")
    .select("id")
    .eq("id", businessId)
    .eq("user_id", userId)
    .single();

  if (error || !data) return `Business ${businessId} not found or not owned by this user.`;
  return null;
}

// ---------------------------------------------------------------------------
// Public helpers
// ---------------------------------------------------------------------------

export async function getToolPermissionsForBusiness(
  businessId: string
): Promise<Result<ToolPermissionView[]>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("tool_permissions")
    .select("*")
    .eq("business_id", businessId)
    .order("created_at", { ascending: true });

  if (error) return err(error.message);
  return ok((data ?? []) as ToolPermissionView[]);
}

export async function getToolPermissionById(
  id: string
): Promise<Result<ToolPermissionView>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("tool_permissions")
    .select("*")
    .eq("id", id)
    .single();

  if (error) return err(error.message);
  if (!data) return err(`Tool permission ${id} not found.`);
  return ok(data as ToolPermissionView);
}

export async function seedToolPermissionsForBusiness(
  businessId: string,
  userId: string
): Promise<Result<ToolPermissionSeedResult>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  // Check ownership
  const ownershipError = await verifyBusinessOwnership(businessId, userId);
  if (ownershipError) return err(ownershipError);

  // Fetch already-seeded tool_ids for this business
  const { data: existing, error: fetchError } = await supabase
    .from("tool_permissions")
    .select("tool_id")
    .eq("business_id", businessId);

  if (fetchError) return err(fetchError.message);

  const existingToolIds = new Set((existing ?? []).map((r: { tool_id: string }) => r.tool_id));

  // Build inserts only for tools not yet present
  const inserts: NewToolPermissionInput[] = [];
  for (const tool of toolRegistry) {
    if (existingToolIds.has(tool.id)) continue;

    const { status, setup_status } = getInitialStatusForTool(tool);

    inserts.push({
      user_id: userId,
      business_id: businessId,
      tool_id: tool.id,
      tool_name: tool.name,
      status,
      setup_status,
      risk_level: normalizeRiskLevel(tool.riskLevel),
      permissions: tool.defaultPermissions,
    });
  }

  const skipped = existingToolIds.size;

  if (inserts.length === 0) {
    // All tools already seeded — return existing records
    const { data: allRecords, error: allError } = await supabase
      .from("tool_permissions")
      .select("*")
      .eq("business_id", businessId)
      .order("created_at", { ascending: true });

    if (allError) return err(allError.message);

    return ok({
      seeded: 0,
      skipped,
      records: (allRecords ?? []) as ToolPermissionView[],
    });
  }

  const { error: insertError } = await supabase
    .from("tool_permissions")
    .insert(inserts as unknown as Record<string, unknown>[]);

  if (insertError) return err(insertError.message);

  // Return all records (existing + newly inserted)
  const { data: allRecords, error: allError } = await supabase
    .from("tool_permissions")
    .select("*")
    .eq("business_id", businessId)
    .order("created_at", { ascending: true });

  if (allError) return err(allError.message);

  return ok({
    seeded: inserts.length,
    skipped,
    records: (allRecords ?? []) as ToolPermissionView[],
  });
}

export async function updateToolPermissionStatus(
  input: ToolPermissionUpdateInput
): Promise<Result<ToolPermissionView>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  // Fetch the record first to verify ownership
  const { data: existing, error: fetchError } = await supabase
    .from("tool_permissions")
    .select("*")
    .eq("id", input.id)
    .single();

  if (fetchError || !existing) return err(`Tool permission ${input.id} not found.`);

  const record = existing as ToolPermissionRecord;
  if (record.user_id !== input.userId) return err("Forbidden.");

  const transition = actionStatusMap[input.action];

  const { data: updated, error: updateError } = await supabase
    .from("tool_permissions")
    .update({
      status: transition.status,
      setup_status: transition.setup_status,
      updated_at: new Date().toISOString(),
    })
    .eq("id", input.id)
    .select()
    .single();

  if (updateError || !updated) return err(updateError?.message ?? "Update failed.");
  return ok(updated as ToolPermissionView);
}

export async function getToolPermissionSummaryForBusiness(
  businessId: string
): Promise<
  Result<{
    total: number;
    by_status: Record<string, number>;
    by_risk: Record<string, number>;
    ready_to_connect: number;
    human_required: number;
  }>
> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("tool_permissions")
    .select("status, risk_level")
    .eq("business_id", businessId);

  if (error) return err(error.message);

  const records = (data ?? []) as { status: string; risk_level: string }[];

  const by_status: Record<string, number> = {};
  const by_risk: Record<string, number> = {};

  for (const r of records) {
    by_status[r.status] = (by_status[r.status] ?? 0) + 1;
    by_risk[r.risk_level] = (by_risk[r.risk_level] ?? 0) + 1;
  }

  return ok({
    total: records.length,
    by_status,
    by_risk,
    ready_to_connect: by_status["ready_to_connect"] ?? 0,
    human_required: by_status["human_required"] ?? 0,
  });
}

export interface ActivityLogInput {
  business_id: string;
  user_id: string;
  activity_type: string;
  message: string;
  metadata?: Record<string, unknown>;
}

export async function createToolPermissionActivityLog(
  input: ActivityLogInput
): Promise<Result<{ id: string }>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("agent_activity_logs")
    .insert({
      business_id: input.business_id,
      user_id: input.user_id,
      activity_type: input.activity_type,
      message: input.message,
      metadata: input.metadata ?? {},
    } as unknown as Record<string, unknown>)
    .select("id")
    .single();

  if (error || !data) return err(error?.message ?? "Failed to create activity log.");
  return ok({ id: (data as { id: string }).id });
}
