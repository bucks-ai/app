// POST /api/businesses/[id]/research/evidence   — create evidence record
// Evidence records are append-only (no PATCH). Update via re-creation if needed.

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { createResearchEvidence } from "@/lib/research";
import type { NewResearchEvidenceInput } from "@/types/research";
import { apiError, unauthorized, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import { createResearchEvidenceBodySchema } from "@/lib/schemas/research";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/research/evidence
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

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return unauthorized();
  }

  const rateLimitResult = await limit(`${userResult.data.id}:research-evidence`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return notFound("Business not found.", "business_not_found");
  }

  if (businessResult.data.user_id !== userResult.data.id) {
    return apiError("Access denied.", "forbidden", 403);
  }

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createResearchEvidenceBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewResearchEvidenceInput = {
    business_id: id,
    user_id: userResult.data.id,
    claim: body.claim,
    source: body.source ?? null,
    source_url: body.source_url ?? null,
    evidence_type: body.evidence_type ?? null,
    confidence: body.confidence ?? null,
    notes: body.notes ?? null,
  };

  const result = await createResearchEvidence(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return apiError(result.error ?? "Could not create evidence record.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}
