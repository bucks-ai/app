import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { createValidationPersona, updateValidationPersona } from "@/lib/validation";
import type {
  NewValidationPersonaInput,
  UpdateValidationPersonaInput,
} from "@/types/validation";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

function authGuard() {
  if (!hasSupabaseEnv()) {
    return errorResponse("Supabase is not configured.", "missing_supabase_env", 503);
  }
  return null;
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/validation/personas
// Body: NewValidationPersonaInput (minus business_id and user_id)
// ---------------------------------------------------------------------------

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const guard = authGuard();
  if (guard) return guard;

  const { id } = await params;
  if (!id) return errorResponse("Business id is required.", "invalid_input", 400);

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return errorResponse("Authentication required.", "unauthenticated", 401);
  }

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "not_found", 404);
  }

  if (businessResult.data.user_id !== userResult.data.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  let body: Record<string, unknown> = {};
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse("Invalid JSON body.", "invalid_input", 400);
  }

  const name = body.name as string | undefined;
  if (!name?.trim()) {
    return errorResponse("name is required.", "invalid_input", 400);
  }

  const input: NewValidationPersonaInput = {
    business_id: id,
    user_id: userResult.data.id,
    name: name.trim(),
    role: (body.role as string | null) ?? null,
    company_type: (body.company_type as string | null) ?? null,
    pain_points: Array.isArray(body.pain_points)
      ? (body.pain_points as string[])
      : null,
    goals: Array.isArray(body.goals) ? (body.goals as string[]) : null,
    notes: (body.notes as string | null) ?? null,
    priority:
      body.priority === "high" || body.priority === "low" ? body.priority : "medium",
  };

  const result = await createValidationPersona(input);

  if (result.error || !result.data) {
    const code = result.code ?? "create_error";
    if (code === "validation_schema_missing") {
      return errorResponse(result.error ?? "Validation schema missing.", code, 503);
    }
    return errorResponse(result.error ?? "Could not create persona.", code, 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}

// ---------------------------------------------------------------------------
// PATCH /api/businesses/[id]/validation/personas
// Body: UpdateValidationPersonaInput (must include id)
// ---------------------------------------------------------------------------

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const guard = authGuard();
  if (guard) return guard;

  const { id } = await params;
  if (!id) return errorResponse("Business id is required.", "invalid_input", 400);

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return errorResponse("Authentication required.", "unauthenticated", 401);
  }

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "not_found", 404);
  }

  if (businessResult.data.user_id !== userResult.data.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  let body: Record<string, unknown> = {};
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse("Invalid JSON body.", "invalid_input", 400);
  }

  const personaId = body.id as string | undefined;
  if (!personaId?.trim()) {
    return errorResponse("id is required.", "invalid_input", 400);
  }

  const input: UpdateValidationPersonaInput = {
    id: personaId.trim(),
    business_id: id,
    ...(body.name !== undefined && { name: body.name as string }),
    ...(body.role !== undefined && { role: body.role as string | null }),
    ...(body.company_type !== undefined && {
      company_type: body.company_type as string | null,
    }),
    ...(body.pain_points !== undefined && {
      pain_points: Array.isArray(body.pain_points)
        ? (body.pain_points as string[])
        : null,
    }),
    ...(body.goals !== undefined && {
      goals: Array.isArray(body.goals) ? (body.goals as string[]) : null,
    }),
    ...(body.notes !== undefined && { notes: body.notes as string | null }),
    ...(body.priority !== undefined && {
      priority:
        body.priority === "high" || body.priority === "low" ? body.priority : "medium",
    }),
  };

  const result = await updateValidationPersona(input);

  if (result.error || !result.data) {
    const code = result.code ?? "update_error";
    if (code === "validation_schema_missing") {
      return errorResponse(result.error ?? "Validation schema missing.", code, 503);
    }
    return errorResponse(result.error ?? "Could not update persona.", code, 500);
  }

  return Response.json({ ok: true, data: result.data });
}
