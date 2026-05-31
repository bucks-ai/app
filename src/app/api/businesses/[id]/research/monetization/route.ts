// POST  /api/businesses/[id]/research/monetization   — create monetization model
// PATCH /api/businesses/[id]/research/monetization   — update model (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import {
  createResearchMonetizationModel,
  updateResearchMonetizationModel,
} from "@/lib/research";
import type {
  NewResearchMonetizationModelInput,
  UpdateResearchMonetizationModelInput,
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

  const model = typeof body.model === "string" ? body.model.trim() : "";
  if (!model) return errorResponse("model is required.", "invalid_input", 400);

  const rawConfidence = body.confidence as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: NewResearchMonetizationModelInput = {
    business_id: id,
    user_id: user.id,
    model,
    buyer: (body.buyer as string | null) ?? null,
    price_assumption: (body.price_assumption as string | null) ?? null,
    value_metric: (body.value_metric as string | null) ?? null,
    reasoning: (body.reasoning as string | null) ?? null,
    confidence: VALID_CONFIDENCES.has(rawConfidence as ResearchConfidence)
      ? (rawConfidence as ResearchConfidence)
      : null,
    priority: VALID_PRIORITIES.has(rawPriority as ResearchPriority)
      ? (rawPriority as ResearchPriority)
      : "medium",
  };

  const result = await createResearchMonetizationModel(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return errorResponse(result.error ?? "Could not create monetization model.", code,
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

  const modelId = typeof body.id === "string" ? body.id.trim() : "";
  if (!modelId) return errorResponse("id (model uuid) is required.", "invalid_input", 400);

  const rawConfidence = body.confidence as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: UpdateResearchMonetizationModelInput = {
    id: modelId,
    business_id: id,
    ...(body.model !== undefined && { model: body.model as string }),
    ...(body.buyer !== undefined && { buyer: body.buyer as string | null }),
    ...(body.price_assumption !== undefined && { price_assumption: body.price_assumption as string | null }),
    ...(body.value_metric !== undefined && { value_metric: body.value_metric as string | null }),
    ...(body.reasoning !== undefined && { reasoning: body.reasoning as string | null }),
    ...(rawConfidence !== undefined &&
      VALID_CONFIDENCES.has(rawConfidence as ResearchConfidence) && {
        confidence: rawConfidence as ResearchConfidence,
      }),
    ...(rawPriority !== undefined &&
      VALID_PRIORITIES.has(rawPriority as ResearchPriority) && {
        priority: rawPriority as ResearchPriority,
      }),
  };

  const result = await updateResearchMonetizationModel(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return errorResponse(result.error ?? "Could not update monetization model.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
