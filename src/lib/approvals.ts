// Server-side helpers for the in-app Approval Queue (M4a).
// Mirrors runner/langgraph/tools/app_approvals_daemon.py's Supabase side:
// the runner upserts pending rows into `approvals` from outbox/, the app
// lists/decides them here, and the runner polls decided rows to write the
// same inbox/ fulfillment file the Slack daemon would write.
//
// Not business-scoped: these rows belong to the operator account (owner-only
// RLS — see supabase/m4a-approvals-queue.sql), not any one founder's
// business, so every helper here is scoped by user_id, never business_id.
//
// All functions are server-only — do not import from client components.

import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { ApprovalRecord } from "@/types/database";

// ---------------------------------------------------------------------------
// Result wrapper (consistent with tool-permissions.ts / projects.ts)
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

function isSchemaMissing(error: { code?: string; message?: string } | null): boolean {
  if (!error) return false;
  const msg = error.message ?? "";
  return error.code === "42P01" || msg.includes("does not exist") || msg.includes("approvals");
}

// PostgREST's code for .single() matching zero (or more than one) rows.
const NOT_FOUND_CODE = "PGRST116";

// ---------------------------------------------------------------------------
// Actions — the only two decisions the app can make on a pending request
// ---------------------------------------------------------------------------

export type ApprovalAction = "approve" | "reject";

const ACTION_TO_STATUS: Record<ApprovalAction, string> = {
  approve: "approved",
  reject: "rejected",
};

// ---------------------------------------------------------------------------
// Read helpers
// ---------------------------------------------------------------------------

export async function getPendingApprovalsForOwner(
  userId: string
): Promise<Result<ApprovalRecord[]>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "supabase_not_configured");

  const { data, error } = await supabase
    .from("approvals")
    .select("*")
    .eq("user_id", userId)
    .eq("status", "pending")
    .order("created_at", { ascending: true });

  if (error) {
    if (isSchemaMissing(error)) {
      return err(
        "approvals table does not exist. Apply supabase/m4a-approvals-queue.sql first.",
        "approvals_schema_missing"
      );
    }
    return err(error.message, "approvals_fetch_failed");
  }

  return ok((data ?? []) as ApprovalRecord[]);
}

export async function getApprovalById(id: string): Promise<Result<ApprovalRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "supabase_not_configured");

  const { data, error } = await supabase.from("approvals").select("*").eq("id", id).single();

  if (error) {
    if (isSchemaMissing(error)) {
      return err(
        "approvals table does not exist. Apply supabase/m4a-approvals-queue.sql first.",
        "approvals_schema_missing"
      );
    }
    if (error.code === NOT_FOUND_CODE) {
      return err(`Approval ${id} not found.`, "not_found");
    }
    return err(error.message, "approval_fetch_failed");
  }
  if (!data) return err(`Approval ${id} not found.`, "not_found");

  return ok(data as ApprovalRecord);
}

// ---------------------------------------------------------------------------
// Write helpers
// ---------------------------------------------------------------------------

export interface UpdateApprovalDecisionInput {
  id: string;
  action: ApprovalAction;
  userId: string;
  decidedBy: string;
}

/**
 * Idempotent with both re-clicks in the app and the Slack daemon: only
 * flips status while it is still "pending" (a compare-and-swap via the
 * .eq("status", "pending") filter). If another channel already decided it,
 * this is a no-op that returns the row's current (already-decided) state
 * rather than erroring — the inbox-file write itself is where the true
 * existence-check race is resolved, on the runner side.
 */
export async function updateApprovalDecision(
  input: UpdateApprovalDecisionInput
): Promise<Result<ApprovalRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "supabase_not_configured");

  const existingResult = await getApprovalById(input.id);
  if (existingResult.error || !existingResult.data) {
    return err(existingResult.error ?? "Approval not found.", existingResult.code ?? "not_found");
  }
  const existing = existingResult.data;

  if (existing.user_id !== input.userId) {
    return err("Forbidden.", "forbidden");
  }

  if (existing.status !== "pending") {
    // Already decided (by this user or the Slack daemon) — idempotent no-op.
    return ok(existing);
  }

  const { data, error } = await supabase
    .from("approvals")
    .update({
      status: ACTION_TO_STATUS[input.action],
      decided_by: input.decidedBy,
      decided_at: new Date().toISOString(),
    })
    .eq("id", input.id)
    .eq("status", "pending")
    .select()
    .single();

  if (error || !data) {
    // Lost the compare-and-swap race (another request flipped it first) —
    // treat identically to the already-decided branch above.
    const refetched = await getApprovalById(input.id);
    if (refetched.data) return ok(refetched.data);
    return err(error?.message ?? "Update failed.", "approval_update_failed");
  }

  return ok(data as ApprovalRecord);
}
