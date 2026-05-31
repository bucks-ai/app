// POST /api/businesses/[id]/research/evidence   — create evidence record
// Evidence records are append-only (no PATCH). Update via re-creation if needed.

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { createResearchEvidence } from "@/lib/research";
import type {
  NewResearchEvidenceInput,
  ResearchConfidence,
} from "@/types/research";

const VALID_CONFIDENCES = new Set<ResearchConfidence>([
  "assumption", "weak_signal", "medium_signal", "strong_signal", "validated", "invalidated",
]);
const VALID_EVIDENCE_TYPES = new Set([
  "data_point", "quote", "case_study", "trend",
  "competitor_signal", "customer_signal", "market_report",
]);

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/research/evidence
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

  const claim = typeof body.claim === "string" ? body.claim.trim() : "";
  if (!claim) return errorResponse("claim is required.", "invalid_input", 400);

  const rawEvidenceType = body.evidence_type as string | undefined;
  const rawConfidence = body.confidence as string | undefined;

  const input: NewResearchEvidenceInput = {
    business_id: id,
    user_id: userResult.data.id,
    claim,
    source: (body.source as string | null) ?? null,
    source_url: (body.source_url as string | null) ?? null,
    evidence_type:
      rawEvidenceType && VALID_EVIDENCE_TYPES.has(rawEvidenceType) ? rawEvidenceType : null,
    confidence: VALID_CONFIDENCES.has(rawConfidence as ResearchConfidence)
      ? (rawConfidence as ResearchConfidence)
      : null,
    notes: (body.notes as string | null) ?? null,
  };

  const result = await createResearchEvidence(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return errorResponse(result.error ?? "Could not create evidence record.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}
