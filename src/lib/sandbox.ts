// Server-side helpers for per-business sandbox configuration (M4b
// containment substrate). All functions are server-only — do not import
// from client components.
//
// CRITICAL SAFETY: business_sandbox stores SECRET NAMES ONLY, never secret
// values. github_token_secret_name / vercel_token_secret_name name an entry
// in the runner's own env/secret store — the actual tokens never pass
// through this file, the database, or any API route built on top of it. See
// supabase/migrations/README.md for the full convention writeup.

import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { BusinessSandboxRecord, SandboxStatus } from "@/types/database";
import {
  SANDBOX_FIELDS,
  SANDBOX_FIELD_LABELS,
  type SandboxFieldKey,
  type SandboxFieldView,
} from "@/types/sandbox-ui";

// ---------------------------------------------------------------------------
// Result wrapper (consistent with projects.ts / tool-permissions.ts)
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
// Pure helpers — no I/O, unit-tested directly.
// ---------------------------------------------------------------------------

type SandboxFieldValues = Partial<Record<SandboxFieldKey, string | null | undefined>>;

/** unconfigured -> partial -> configured, derived from which fields are set. */
export function computeSandboxStatus(fields: SandboxFieldValues): SandboxStatus {
  const setCount = SANDBOX_FIELDS.filter((key) => Boolean(fields[key]?.trim())).length;
  if (setCount === 0) return "unconfigured";
  if (setCount === SANDBOX_FIELDS.length) return "configured";
  return "partial";
}

/**
 * Per-field configured/unconfigured breakdown for the Settings tab.
 * Every returned `value` is a NAME (repo name, project id, secret name),
 * never a secret value — business_sandbox never stores one.
 */
export function getSandboxFieldStatuses(
  record: SandboxFieldValues | null
): SandboxFieldView[] {
  return SANDBOX_FIELDS.map((field) => {
    const value = record?.[field]?.trim() || null;
    return {
      field,
      label: SANDBOX_FIELD_LABELS[field],
      configured: Boolean(value),
      value,
    };
  });
}

// ---------------------------------------------------------------------------
// Data access
// ---------------------------------------------------------------------------

export async function getSandboxConfigForBusiness(
  businessId: string
): Promise<Result<BusinessSandboxRecord | null>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const { data, error } = await supabase
    .from("business_sandbox")
    .select("*")
    .eq("business_id", businessId)
    .maybeSingle();

  if (error) return err(error.message);
  return ok((data as BusinessSandboxRecord | null) ?? null);
}

export type SandboxConfigUpdate = Partial<
  Pick<
    BusinessSandboxRecord,
    | "repo_full_name"
    | "vercel_project_id"
    | "github_token_secret_name"
    | "vercel_token_secret_name"
  >
>;

/**
 * Upserts the business's sandbox row (business_id is unique). Merges the
 * given updates onto any existing row rather than clobbering fields the
 * founder isn't touching in this call, so fields can be set one at a time.
 */
export async function upsertSandboxConfig(
  businessId: string,
  userId: string,
  updates: SandboxConfigUpdate
): Promise<Result<BusinessSandboxRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT);

  const existingResult = await getSandboxConfigForBusiness(businessId);
  if (existingResult.error) return err(existingResult.error);
  const existing = existingResult.data;

  const merged: SandboxConfigUpdate = {
    repo_full_name: updates.repo_full_name ?? existing?.repo_full_name ?? null,
    vercel_project_id: updates.vercel_project_id ?? existing?.vercel_project_id ?? null,
    github_token_secret_name:
      updates.github_token_secret_name ?? existing?.github_token_secret_name ?? null,
    vercel_token_secret_name:
      updates.vercel_token_secret_name ?? existing?.vercel_token_secret_name ?? null,
  };

  const { data, error } = await supabase
    .from("business_sandbox")
    .upsert(
      {
        business_id: businessId,
        user_id: userId,
        ...merged,
        status: computeSandboxStatus(merged),
        updated_at: new Date().toISOString(),
      },
      { onConflict: "business_id" }
    )
    .select()
    .single();

  if (error) return err(error.message);
  if (!data) return err("Failed to save sandbox configuration.");
  return ok(data as BusinessSandboxRecord);
}
