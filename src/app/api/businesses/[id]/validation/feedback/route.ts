// POST /api/businesses/[id]/validation/feedback   — create structured feedback note

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { createValidationFeedbackNote } from "@/lib/validation";
import type { NewValidationFeedbackNoteInput } from "@/types/validation";
import { badRequest, zodIssuesToFields } from "@/lib/api-error";
import { createValidationFeedbackNoteBodySchema } from "@/lib/schemas/validation";

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

  const { user, response } = await requireUser();
  if (!user) return response;

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }

  if (businessResult.data.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createValidationFeedbackNoteBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewValidationFeedbackNoteInput = {
    business_id: id,
    user_id: user.id,
    summary: body.summary,
    lead_id: body.lead_id ?? null,
    hypothesis_id: body.hypothesis_id ?? null,
    pain_signal: body.pain_signal ?? null,
    willingness_to_pay_signal: body.willingness_to_pay_signal ?? null,
    objections: body.objections ?? null,
    quotes: body.quotes ?? null,
    next_step: body.next_step ?? null,
    signal_strength: body.signal_strength ?? null,
  };

  const result = await createValidationFeedbackNote(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_create_failed";
    return errorResponse(result.error ?? "Could not create feedback note.", code,
      code === "validation_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}
