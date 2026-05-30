// POST  /api/businesses/[id]/validation/personas   — create persona
// PATCH /api/businesses/[id]/validation/personas   — update persona (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { createValidationPersona, updateValidationPersona } from "@/lib/validation";
import type {
  NewValidationPersonaInput,
  UpdateValidationPersonaInput,
  ValidationPriority,
} from "@/types/validation";

const VALID_PRIORITIES = new Set<ValidationPriority>(["high", "medium", "low"]);

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

async function resolveAuth(id: string) {
  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) return { user: null, business: null };

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) return { user: userResult.data, business: null };

  return { user: userResult.data, business: businessResult.data };
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

  const { user, business } = await resolveAuth(id);
  if (!user) return errorResponse("Authentication required.", "unauthenticated", 401);
  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let body: Record<string, unknown> = {};
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse("Invalid JSON body.", "invalid_input", 400);
  }

  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (!name) return errorResponse("name is required.", "invalid_input", 400);

  const rawPriority = body.priority as string | undefined;

  const input: NewValidationPersonaInput = {
    business_id: id,
    user_id: user.id,
    name,
    segment: (body.segment as string | null) ?? null,
    description: (body.description as string | null) ?? null,
    pain_points: Array.isArray(body.pain_points) ? (body.pain_points as string[]) : null,
    desired_outcomes: Array.isArray(body.desired_outcomes)
      ? (body.desired_outcomes as string[])
      : null,
    channels: Array.isArray(body.channels) ? (body.channels as string[]) : null,
    willingness_to_pay: (body.willingness_to_pay as string | null) ?? null,
    priority: VALID_PRIORITIES.has(rawPriority as ValidationPriority)
      ? (rawPriority as ValidationPriority)
      : "medium",
    status: typeof body.status === "string" ? body.status : "active",
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

  const { user, business } = await resolveAuth(id);
  if (!user) return errorResponse("Authentication required.", "unauthenticated", 401);
  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let body: Record<string, unknown> = {};
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse("Invalid JSON body.", "invalid_input", 400);
  }

  const personaId = typeof body.id === "string" ? body.id.trim() : "";
  if (!personaId) return errorResponse("id (persona uuid) is required.", "invalid_input", 400);

  const rawPriority = body.priority as string | undefined;

  const input: UpdateValidationPersonaInput = {
    id: personaId,
    business_id: id,
    ...(body.name !== undefined && { name: body.name as string }),
    ...(body.segment !== undefined && { segment: body.segment as string | null }),
    ...(body.description !== undefined && { description: body.description as string | null }),
    ...(body.pain_points !== undefined && {
      pain_points: Array.isArray(body.pain_points) ? (body.pain_points as string[]) : null,
    }),
    ...(body.desired_outcomes !== undefined && {
      desired_outcomes: Array.isArray(body.desired_outcomes)
        ? (body.desired_outcomes as string[])
        : null,
    }),
    ...(body.channels !== undefined && {
      channels: Array.isArray(body.channels) ? (body.channels as string[]) : null,
    }),
    ...(body.willingness_to_pay !== undefined && {
      willingness_to_pay: body.willingness_to_pay as string | null,
    }),
    ...(rawPriority !== undefined &&
      VALID_PRIORITIES.has(rawPriority as ValidationPriority) && {
        priority: rawPriority as ValidationPriority,
      }),
    ...(body.status !== undefined && { status: body.status as string }),
  };

  const result = await updateValidationPersona(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_update_failed";
    return errorResponse(result.error ?? "Could not update persona.", code,
      code === "validation_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
