// GET /api/businesses/[id]/sandbox
// Returns the business's sandbox configuration status: unconfigured/partial/
// configured plus a per-field configured/unconfigured breakdown for the
// Settings tab. Every field value returned is a NAME (repo name, Vercel
// project id, secret name) — business_sandbox never stores a secret value,
// so there is never one to leak here.
//
// PATCH /api/businesses/[id]/sandbox
// Founder-only: sets one or more of repo_full_name, vercel_project_id,
// github_token_secret_name, vercel_token_secret_name. Partial updates are
// merged onto the existing row (src/lib/sandbox.ts::upsertSandboxConfig), so
// the founder can configure fields one at a time.
//
// Response shapes:
//   success: { ok: true, data: { sandbox: SandboxConfigView } }
//   error:   { ok: false, code: string, error: string }

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import {
  getSandboxConfigForBusiness,
  getSandboxFieldStatuses,
  upsertSandboxConfig,
} from "@/lib/sandbox";
import { apiError, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import {
  businessSandboxParamsSchema,
  setBusinessSandboxBodySchema,
} from "@/lib/schemas/infra";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";
import type { SandboxConfigView } from "@/types/sandbox-ui";
import type { BusinessSandboxRecord } from "@/types/database";

async function resolveOwnedBusiness(id: string, userId: string) {
  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return { error: notFound("Business not found.", "business_not_found") };
  }
  if (businessResult.data.user_id !== userId) {
    return { error: apiError("Access denied.", "forbidden", 403) };
  }
  return { business: businessResult.data };
}

function toSandboxConfigView(record: BusinessSandboxRecord | null): SandboxConfigView {
  return {
    status: record?.status ?? "unconfigured",
    fields: getSandboxFieldStatuses(record),
    updatedAt: record?.updated_at ?? null,
  };
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const rawParams = await params;
  const parsedParams = businessSandboxParamsSchema.safeParse(rawParams);
  if (!parsedParams.success) {
    return badRequest(
      "Request path failed validation.",
      "validation_error",
      zodIssuesToFields(parsedParams.error),
    );
  }
  const { id } = parsedParams.data;

  const { user, response } = await requireUser();
  if (!user) return response;

  const owned = await resolveOwnedBusiness(id, user.id);
  if (owned.error) return owned.error;

  const sandboxResult = await getSandboxConfigForBusiness(id);
  if (sandboxResult.error) {
    return apiError(sandboxResult.error, "sandbox_fetch_failed", 500);
  }

  return Response.json({
    ok: true,
    data: { sandbox: toSandboxConfigView(sandboxResult.data) },
  });
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const rawParams = await params;
  const parsedParams = businessSandboxParamsSchema.safeParse(rawParams);
  if (!parsedParams.success) {
    return badRequest(
      "Request path failed validation.",
      "validation_error",
      zodIssuesToFields(parsedParams.error),
    );
  }
  const { id } = parsedParams.data;

  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:sandbox-update`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsedBody = setBusinessSandboxBodySchema.safeParse(json);
  if (!parsedBody.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsedBody.error),
    );
  }

  const owned = await resolveOwnedBusiness(id, user.id);
  if (owned.error) return owned.error;

  const updateResult = await upsertSandboxConfig(id, user.id, parsedBody.data);
  if (updateResult.error || !updateResult.data) {
    return apiError(updateResult.error ?? "Could not save sandbox configuration.", "sandbox_update_failed", 500);
  }

  return Response.json({
    ok: true,
    data: { sandbox: toSandboxConfigView(updateResult.data) },
  });
}
