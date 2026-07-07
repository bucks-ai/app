// GET  /api/businesses/[id]/validation   — return full validation workspace
// POST /api/businesses/[id]/validation   — seed workspace from blueprint

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import {
  getValidationWorkspace,
  seedValidationWorkspaceFromBlueprint,
} from "@/lib/validation";
import { apiError, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import { seedValidationBodySchema } from "@/lib/schemas/validation";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

// ---------------------------------------------------------------------------
// GET /api/businesses/[id]/validation
// ---------------------------------------------------------------------------

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { id } = await params;
  if (!id) return badRequest("Business id is required.", "invalid_input");

  const { user, response } = await requireUser();
  if (!user) return response;

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return notFound("Business not found.", "business_not_found");
  }

  if (businessResult.data.user_id !== user.id) {
    return apiError("Access denied.", "forbidden", 403);
  }

  const result = await getValidationWorkspace(id);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_error";
    const httpStatus = code === "validation_schema_missing" ? 503 : 500;
    return apiError(
      result.error ?? "Could not load validation workspace.",
      code,
      httpStatus
    );
  }

  return Response.json({ ok: true, data: result.data });
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/validation
// Body: { action: "seed" }
// ---------------------------------------------------------------------------

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { id } = await params;
  if (!id) return badRequest("Business id is required.", "invalid_input");

  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:validation-seed`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return notFound("Business not found.", "business_not_found");
  }

  if (businessResult.data.user_id !== user.id) {
    return apiError("Access denied.", "forbidden", 403);
  }

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = seedValidationBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const result = await seedValidationWorkspaceFromBlueprint(id);

  if (result.error || !result.data) {
    const code = result.code ?? "seed_failed";
    const httpStatus = code === "validation_schema_missing" ? 503 : 500;
    return apiError(
      result.error ?? "Could not seed validation workspace.",
      code,
      httpStatus
    );
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}
