// POST  /api/businesses/[id]/research/hypotheses   — create research hypothesis
// PATCH /api/businesses/[id]/research/hypotheses   — update hypothesis (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import {
  createResearchHypothesis,
  updateResearchHypothesis,
} from "@/lib/research";
import type {
  NewResearchHypothesisInput,
  UpdateResearchHypothesisInput,
  ResearchConfidence,
  ResearchPriority,
} from "@/types/research";

const VALID_CONFIDENCES = new Set<ResearchConfidence>([
  "assumption", "weak_signal", "medium_signal", "strong_signal", "validated", "invalidated",
]);
const VALID_PRIORITIES = new Set<ResearchPriority>(["high", "medium", "low"]);

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

  const rawConfidence = body.confidence as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: NewResearchHypothesisInput = {
    business_id: id,
    user_id: user.id,
    title,
    description: (body.description as string | null) ?? null,
    test_method: (body.test_method as string | null) ?? null,
    success_criteria: (body.success_criteria as string | null) ?? null,
    confidence: VALID_CONFIDENCES.has(rawConfidence as ResearchConfidence)
      ? (rawConfidence as ResearchConfidence)
      : null,
    priority: VALID_PRIORITIES.has(rawPriority as ResearchPriority)
      ? (rawPriority as ResearchPriority)
      : "medium",
  };

  const result = await createResearchHypothesis(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return errorResponse(result.error ?? "Could not create research hypothesis.", code,
      code === "research_schema_missing" ? 503 : 500);
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

  const rawConfidence = body.confidence as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: UpdateResearchHypothesisInput = {
    id: hypothesisId,
    business_id: id,
    ...(body.title !== undefined && { title: body.title as string }),
    ...(body.description !== undefined && { description: body.description as string | null }),
    ...(body.test_method !== undefined && { test_method: body.test_method as string | null }),
    ...(body.success_criteria !== undefined && { success_criteria: body.success_criteria as string | null }),
    ...(rawConfidence !== undefined &&
      VALID_CONFIDENCES.has(rawConfidence as ResearchConfidence) && {
        confidence: rawConfidence as ResearchConfidence,
      }),
    ...(rawPriority !== undefined &&
      VALID_PRIORITIES.has(rawPriority as ResearchPriority) && {
        priority: rawPriority as ResearchPriority,
      }),
  };

  const result = await updateResearchHypothesis(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return errorResponse(result.error ?? "Could not update research hypothesis.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
