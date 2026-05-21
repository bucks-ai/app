import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { createValidationFeedbackNote } from "@/lib/validation";
import type {
  NewValidationFeedbackNoteInput,
  ValidationSentiment,
} from "@/types/validation";

const VALID_SENTIMENTS = new Set<ValidationSentiment>([
  "positive",
  "negative",
  "neutral",
]);

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/validation/feedback
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

  const note = body.note as string | undefined;
  if (!note?.trim()) {
    return errorResponse("note is required.", "invalid_input", 400);
  }

  const rawSentiment = body.sentiment as string | undefined;
  const sentiment: ValidationSentiment | null =
    rawSentiment && VALID_SENTIMENTS.has(rawSentiment as ValidationSentiment)
      ? (rawSentiment as ValidationSentiment)
      : null;

  const input: NewValidationFeedbackNoteInput = {
    business_id: id,
    user_id: userResult.data.id,
    note: note.trim(),
    sentiment,
    lead_id: (body.lead_id as string | null) ?? null,
    persona_id: (body.persona_id as string | null) ?? null,
    hypothesis_id: (body.hypothesis_id as string | null) ?? null,
  };

  const result = await createValidationFeedbackNote(input);

  if (result.error || !result.data) {
    const code = result.code ?? "create_error";
    if (code === "validation_schema_missing") {
      return errorResponse(result.error ?? "Validation schema missing.", code, 503);
    }
    return errorResponse(result.error ?? "Could not create feedback note.", code, 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}
