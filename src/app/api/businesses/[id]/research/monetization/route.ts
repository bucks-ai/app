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
} from "@/types/research";
import { apiError, unauthorized, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import {
  createResearchMonetizationModelBodySchema,
  updateResearchMonetizationModelBodySchema,
} from "@/lib/schemas/research";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

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
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { id } = await params;
  if (!id) return badRequest("Business id is required.", "invalid_input");

  const { user, business } = await resolveAuth(id);
  if (!user) return unauthorized();

  const rateLimitResult = await limit(`${user.id}:research-monetization`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return notFound("Business not found.", "business_not_found");
  if (business.user_id !== user.id) return apiError("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createResearchMonetizationModelBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewResearchMonetizationModelInput = {
    business_id: id,
    user_id: user.id,
    model: body.model,
    buyer: body.buyer ?? null,
    price_assumption: body.price_assumption ?? null,
    value_metric: body.value_metric ?? null,
    reasoning: body.reasoning ?? null,
    confidence: body.confidence ?? null,
    priority: body.priority ?? "medium",
  };

  const result = await createResearchMonetizationModel(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return apiError(result.error ?? "Could not create monetization model.", code,
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
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { id } = await params;
  if (!id) return badRequest("Business id is required.", "invalid_input");

  const { user, business } = await resolveAuth(id);
  if (!user) return unauthorized();

  const rateLimitResult = await limit(`${user.id}:research-monetization`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return notFound("Business not found.", "business_not_found");
  if (business.user_id !== user.id) return apiError("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateResearchMonetizationModelBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: UpdateResearchMonetizationModelInput = {
    id: body.id,
    business_id: id,
    ...(body.model !== undefined && { model: body.model }),
    ...(body.buyer !== undefined && { buyer: body.buyer }),
    ...(body.price_assumption !== undefined && { price_assumption: body.price_assumption }),
    ...(body.value_metric !== undefined && { value_metric: body.value_metric }),
    ...(body.reasoning !== undefined && { reasoning: body.reasoning }),
    ...(body.confidence !== undefined && { confidence: body.confidence }),
    ...(body.priority !== undefined && { priority: body.priority }),
  };

  const result = await updateResearchMonetizationModel(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return apiError(result.error ?? "Could not update monetization model.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
