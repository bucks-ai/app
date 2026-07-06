// POST  /api/businesses/[id]/validation/hypotheses   — create hypothesis
// PATCH /api/businesses/[id]/validation/hypotheses   — update hypothesis (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { createValidationHypothesis, updateValidationHypothesis } from "@/lib/validation";
import type {
  NewValidationHypothesisInput,
  UpdateValidationHypothesisInput,
} from "@/types/validation";
import { badRequest, zodIssuesToFields } from "@/lib/api-error";
import {
  createValidationHypothesisBodySchema,
  updateValidationHypothesisBodySchema,
} from "@/lib/schemas/validation";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

async function resolveBusiness(id: string) {
  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) return null;
  return businessResult.data;
}

// ---------------------------------------------------------------------------
// POST
// ---------------------------------------------------------------------------

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return errorResponse("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { id } = await params;
  if (!id) return errorResponse("Business id is required.", "invalid_input", 400);

  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:validation-hypotheses`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  const business = await resolveBusiness(id);
  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createValidationHypothesisBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewValidationHypothesisInput = {
    business_id: id,
    user_id: user.id,
    title: body.title,
    description: body.description ?? null,
    type: body.type ?? null,
    assumption: body.assumption ?? null,
    success_criteria: body.success_criteria ?? null,
    status: body.status ?? "untested",
    confidence: body.confidence ?? null,
    priority: body.priority ?? "medium",
  };

  const result = await createValidationHypothesis(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_create_failed";
    return errorResponse(result.error ?? "Could not create hypothesis.", code,
      code === "validation_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}

// ---------------------------------------------------------------------------
// PATCH
// ---------------------------------------------------------------------------

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return errorResponse("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { id } = await params;
  if (!id) return errorResponse("Business id is required.", "invalid_input", 400);

  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:validation-hypotheses`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  const business = await resolveBusiness(id);
  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateValidationHypothesisBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: UpdateValidationHypothesisInput = {
    id: body.id,
    business_id: id,
    ...(body.title !== undefined && { title: body.title }),
    ...(body.description !== undefined && { description: body.description }),
    ...(body.type !== undefined && { type: body.type }),
    ...(body.assumption !== undefined && { assumption: body.assumption }),
    ...(body.success_criteria !== undefined && { success_criteria: body.success_criteria }),
    ...(body.status !== undefined && { status: body.status }),
    ...(body.confidence !== undefined && { confidence: body.confidence }),
    ...(body.priority !== undefined && { priority: body.priority }),
  };

  const result = await updateValidationHypothesis(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_update_failed";
    return errorResponse(result.error ?? "Could not update hypothesis.", code,
      code === "validation_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
