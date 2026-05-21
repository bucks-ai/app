import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { createValidationHypothesis, updateValidationHypothesis } from "@/lib/validation";
import type {
  NewValidationHypothesisInput,
  UpdateValidationHypothesisInput,
  ValidationHypothesisStatus,
} from "@/types/validation";

const VALID_STATUSES = new Set<ValidationHypothesisStatus>([
  "untested",
  "testing",
  "supported",
  "rejected",
  "inconclusive",
]);

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/validation/hypotheses
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

  const statement = body.statement as string | undefined;
  if (!statement?.trim()) {
    return errorResponse("statement is required.", "invalid_input", 400);
  }

  const rawStatus = body.status as string | undefined;
  const status: ValidationHypothesisStatus =
    rawStatus && VALID_STATUSES.has(rawStatus as ValidationHypothesisStatus)
      ? (rawStatus as ValidationHypothesisStatus)
      : "untested";

  const input: NewValidationHypothesisInput = {
    business_id: id,
    user_id: userResult.data.id,
    statement: statement.trim(),
    rationale: (body.rationale as string | null) ?? null,
    status,
  };

  const result = await createValidationHypothesis(input);

  if (result.error || !result.data) {
    const code = result.code ?? "create_error";
    if (code === "validation_schema_missing") {
      return errorResponse(result.error ?? "Validation schema missing.", code, 503);
    }
    return errorResponse(result.error ?? "Could not create hypothesis.", code, 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}

// ---------------------------------------------------------------------------
// PATCH /api/businesses/[id]/validation/hypotheses
// Body: UpdateValidationHypothesisInput (must include id)
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

  const hypothesisId = body.id as string | undefined;
  if (!hypothesisId?.trim()) {
    return errorResponse("id is required.", "invalid_input", 400);
  }

  const rawStatus = body.status as string | undefined;

  const input: UpdateValidationHypothesisInput = {
    id: hypothesisId.trim(),
    business_id: id,
    ...(body.statement !== undefined && { statement: body.statement as string }),
    ...(body.rationale !== undefined && { rationale: body.rationale as string | null }),
    ...(rawStatus !== undefined &&
      VALID_STATUSES.has(rawStatus as ValidationHypothesisStatus) && {
        status: rawStatus as ValidationHypothesisStatus,
      }),
    ...(body.evidence !== undefined && { evidence: body.evidence as string | null }),
  };

  const result = await updateValidationHypothesis(input);

  if (result.error || !result.data) {
    const code = result.code ?? "update_error";
    if (code === "validation_schema_missing") {
      return errorResponse(result.error ?? "Validation schema missing.", code, 503);
    }
    return errorResponse(result.error ?? "Could not update hypothesis.", code, 500);
  }

  return Response.json({ ok: true, data: result.data });
}
