// Status vocabulary and decision writes for human_required_actions.
//
// The table stores free-text status (schema default "pending"), and rows are
// written by several producers — the blueprint parser, the runner, and now the
// founder deciding in the Actions tab — so the open/closed test normalizes
// rather than matching an enum.

import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { HumanRequiredActionRecord } from "@/types/database";
import type { HumanActionDecision } from "@/types/human-action-ui";

const DECISION_TO_STATUS: Record<HumanActionDecision, string> = {
  approve: "approved",
  dismiss: "rejected",
};

const OPEN_HUMAN_ACTION_STATUSES = new Set([
  "pending",
  "open",
  "required",
  "needs_review",
  "needs_approval",
]);

// A decided action is off the founder's plate whichever way it went, so both
// the Actions tab and the execution-status blockers stop counting it.
const CLOSED_HUMAN_ACTION_STATUSES = new Set([
  "approved",
  "rejected",
  "dismissed",
  "cancelled",
  "canceled",
  "complete",
  "completed",
  "resolved",
  "done",
  "closed",
]);

export function isHumanActionOpen(status: string | null | undefined): boolean {
  const normalized = (status ?? "").trim().toLowerCase();
  if (OPEN_HUMAN_ACTION_STATUSES.has(normalized)) return true;
  return !CLOSED_HUMAN_ACTION_STATUSES.has(normalized);
}

type Result<T> =
  | { data: T; error: null; code?: string }
  | { data: null; error: string; code?: string };

function ok<T>(data: T): Result<T> {
  return { data, error: null };
}

function err<T>(message: string, code?: string): Result<T> {
  return { data: null, error: message, code };
}

const NO_CLIENT =
  "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local.";

export async function getHumanRequiredActionById(
  id: string
): Promise<Result<HumanRequiredActionRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "supabase_not_configured");

  const { data, error } = await supabase
    .from("human_required_actions")
    .select("*")
    .eq("id", id)
    .maybeSingle();

  if (error) return err(error.message, "human_action_fetch_failed");
  if (!data) return err("Human action not found.", "not_found");
  return ok(data as HumanRequiredActionRecord);
}

// Records the founder's decision. Re-clicks and races (another tab, the
// runner) are no-ops: an already-decided row is returned as-is.
export async function updateHumanActionDecision(input: {
  id: string;
  decision: HumanActionDecision;
  userId: string;
}): Promise<Result<HumanRequiredActionRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "supabase_not_configured");

  const existingResult = await getHumanRequiredActionById(input.id);
  if (existingResult.error || !existingResult.data) {
    return err(
      existingResult.error ?? "Human action not found.",
      existingResult.code ?? "not_found"
    );
  }

  const existing = existingResult.data;
  if (existing.user_id !== input.userId) {
    return err("Forbidden.", "forbidden");
  }

  if (!isHumanActionOpen(existing.status)) {
    return ok(existing);
  }

  const { data, error } = await supabase
    .from("human_required_actions")
    .update({
      status: DECISION_TO_STATUS[input.decision],
      updated_at: new Date().toISOString(),
    })
    .eq("id", input.id)
    .select()
    .single();

  if (error || !data) {
    const refetched = await getHumanRequiredActionById(input.id);
    if (refetched.data) return ok(refetched.data);
    return err(error?.message ?? "Update failed.", "human_action_update_failed");
  }

  return ok(data as HumanRequiredActionRecord);
}
