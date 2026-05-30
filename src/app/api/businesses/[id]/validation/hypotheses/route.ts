// POST  /api/businesses/[id]/validation/hypotheses   — create hypothesis
// PATCH /api/businesses/[id]/validation/hypotheses   — update hypothesis (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { createValidationHypothesis, updateValidationHypothesis } from "@/lib/validation";
import type {
  NewValidationHypothesisInput,
  UpdateValidationHypothesisInput,
  ValidationHypothesisStatus,
  ValidationHypothesisType,
  ValidationPriority,
} from "@/types/validation";

const VALID_STATUSES = new Set<ValidationHypothesisStatus>([
  "untested", "testing", "supported", "rejected", "inconclusive",
]);
const VALID_TYPES = new Set<ValidationHypothesisType>([
  "customer", "market", "product", "revenue", "other",
]);
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

  const title = typeof body.title === "string" ? body.title.trim() : "";
  if (!title) return errorResponse("title is required.", "invalid_input", 400);

  const rawStatus = body.status as string | undefined;
  const rawType = body.type as string | undefined;
  const rawPriority = body.priority as string | undefined;
  const rawConfidence = body.confidence;

  const input: NewValidationHypothesisInput = {
    business_id: id,
    user_id: user.id,
    title,
    description: (body.description as string | null) ?? null,
    type: VALID_TYPES.has(rawType as ValidationHypothesisType)
      ? (rawType as ValidationHypothesisType)
      : null,
    assumption: (body.assumption as string | null) ?? null,
    success_criteria: (body.success_criteria as string | null) ?? null,
    status: VALID_STATUSES.has(rawStatus as ValidationHypothesisStatus)
      ? (rawStatus as ValidationHypothesisStatus)
      : "untested",
    confidence:
      typeof rawConfidence === "number" && rawConfidence >= 0 && rawConfidence <= 100
        ? rawConfidence
        : null,
    priority: VALID_PRIORITIES.has(rawPriority as ValidationPriority)
      ? (rawPriority as ValidationPriority)
      : "medium",
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

  const hypothesisId = typeof body.id === "string" ? body.id.trim() : "";
  if (!hypothesisId) return errorResponse("id (hypothesis uuid) is required.", "invalid_input", 400);

  const rawStatus = body.status as string | undefined;
  const rawType = body.type as string | undefined;
  const rawPriority = body.priority as string | undefined;
  const rawConfidence = body.confidence;

  const input: UpdateValidationHypothesisInput = {
    id: hypothesisId,
    business_id: id,
    ...(body.title !== undefined && { title: body.title as string }),
    ...(body.description !== undefined && { description: body.description as string | null }),
    ...(rawType !== undefined && {
      type: VALID_TYPES.has(rawType as ValidationHypothesisType)
        ? (rawType as ValidationHypothesisType)
        : null,
    }),
    ...(body.assumption !== undefined && { assumption: body.assumption as string | null }),
    ...(body.success_criteria !== undefined && {
      success_criteria: body.success_criteria as string | null,
    }),
    ...(rawStatus !== undefined &&
      VALID_STATUSES.has(rawStatus as ValidationHypothesisStatus) && {
        status: rawStatus as ValidationHypothesisStatus,
      }),
    ...(rawConfidence !== undefined && {
      confidence:
        typeof rawConfidence === "number" && rawConfidence >= 0 && rawConfidence <= 100
          ? rawConfidence
          : null,
    }),
    ...(rawPriority !== undefined &&
      VALID_PRIORITIES.has(rawPriority as ValidationPriority) && {
        priority: rawPriority as ValidationPriority,
      }),
  };

  const result = await updateValidationHypothesis(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_update_failed";
    return errorResponse(result.error ?? "Could not update hypothesis.", code,
      code === "validation_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
