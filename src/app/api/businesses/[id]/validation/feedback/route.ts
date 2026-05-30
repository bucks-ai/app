// POST /api/businesses/[id]/validation/feedback   — create structured feedback note

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { createValidationFeedbackNote } from "@/lib/validation";
import type {
  NewValidationFeedbackNoteInput,
  ValidationSignalStrength,
} from "@/types/validation";

const VALID_SIGNAL_STRENGTHS = new Set<ValidationSignalStrength>([
  "weak", "medium", "strong",
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
    return errorResponse("Business not found.", "business_not_found", 404);
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

  const summary = typeof body.summary === "string" ? body.summary.trim() : "";
  if (!summary) return errorResponse("summary is required.", "invalid_input", 400);

  const rawSignal = body.signal_strength as string | undefined;

  const input: NewValidationFeedbackNoteInput = {
    business_id: id,
    user_id: userResult.data.id,
    summary,
    lead_id: (body.lead_id as string | null) ?? null,
    hypothesis_id: (body.hypothesis_id as string | null) ?? null,
    pain_signal: (body.pain_signal as string | null) ?? null,
    willingness_to_pay_signal: (body.willingness_to_pay_signal as string | null) ?? null,
    objections: Array.isArray(body.objections) ? (body.objections as string[]) : null,
    quotes: Array.isArray(body.quotes) ? (body.quotes as string[]) : null,
    next_step: (body.next_step as string | null) ?? null,
    signal_strength: VALID_SIGNAL_STRENGTHS.has(rawSignal as ValidationSignalStrength)
      ? (rawSignal as ValidationSignalStrength)
      : null,
  };

  const result = await createValidationFeedbackNote(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_create_failed";
    return errorResponse(result.error ?? "Could not create feedback note.", code,
      code === "validation_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}
