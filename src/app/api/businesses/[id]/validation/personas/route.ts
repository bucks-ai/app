// POST  /api/businesses/[id]/validation/personas   — create persona
// PATCH /api/businesses/[id]/validation/personas   — update persona (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { createValidationPersona, updateValidationPersona } from "@/lib/validation";
import type {
  NewValidationPersonaInput,
  UpdateValidationPersonaInput,
} from "@/types/validation";
import { badRequest, zodIssuesToFields } from "@/lib/api-error";
import {
  createValidationPersonaBodySchema,
  updateValidationPersonaBodySchema,
} from "@/lib/schemas/validation";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

async function resolveBusiness(id: string) {
  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) return null;
  return businessResult.data;
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/validation/personas
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

  const business = await resolveBusiness(id);
  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createValidationPersonaBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewValidationPersonaInput = {
    business_id: id,
    user_id: user.id,
    name: body.name,
    segment: body.segment ?? null,
    description: body.description ?? null,
    pain_points: body.pain_points ?? null,
    desired_outcomes: body.desired_outcomes ?? null,
    channels: body.channels ?? null,
    willingness_to_pay: body.willingness_to_pay ?? null,
    priority: body.priority ?? "medium",
    status: body.status ?? "active",
  };

  const result = await createValidationPersona(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_create_failed";
    return errorResponse(result.error ?? "Could not create persona.", code,
      code === "validation_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}

// ---------------------------------------------------------------------------
// PATCH /api/businesses/[id]/validation/personas
// Body must include: id (the persona uuid to update)
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

  const business = await resolveBusiness(id);
  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateValidationPersonaBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: UpdateValidationPersonaInput = {
    id: body.id,
    business_id: id,
    ...(body.name !== undefined && { name: body.name }),
    ...(body.segment !== undefined && { segment: body.segment }),
    ...(body.description !== undefined && { description: body.description }),
    ...(body.pain_points !== undefined && { pain_points: body.pain_points }),
    ...(body.desired_outcomes !== undefined && { desired_outcomes: body.desired_outcomes }),
    ...(body.channels !== undefined && { channels: body.channels }),
    ...(body.willingness_to_pay !== undefined && { willingness_to_pay: body.willingness_to_pay }),
    ...(body.priority !== undefined && { priority: body.priority }),
    ...(body.status !== undefined && { status: body.status }),
  };

  const result = await updateValidationPersona(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_update_failed";
    return errorResponse(result.error ?? "Could not update persona.", code,
      code === "validation_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
