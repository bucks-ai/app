// POST  /api/businesses/[id]/research/distribution   — create distribution channel
// PATCH /api/businesses/[id]/research/distribution   — update channel (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import {
  createResearchDistributionChannel,
  updateResearchDistributionChannel,
} from "@/lib/research";
import type {
  NewResearchDistributionChannelInput,
  UpdateResearchDistributionChannelInput,
} from "@/types/research";
import { apiError, unauthorized, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import {
  createResearchDistributionChannelBodySchema,
  updateResearchDistributionChannelBodySchema,
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

  const rateLimitResult = await limit(`${user.id}:research-distribution`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return notFound("Business not found.", "business_not_found");
  if (business.user_id !== user.id) return apiError("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createResearchDistributionChannelBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewResearchDistributionChannelInput = {
    business_id: id,
    user_id: user.id,
    channel: body.channel,
    description: body.description ?? null,
    speed_score: body.speed_score ?? null,
    cost_score: body.cost_score ?? null,
    difficulty_score: body.difficulty_score ?? null,
    reasoning: body.reasoning ?? null,
    confidence: body.confidence ?? null,
    priority: body.priority ?? "medium",
  };

  const result = await createResearchDistributionChannel(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return apiError(result.error ?? "Could not create distribution channel.", code,
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

  const rateLimitResult = await limit(`${user.id}:research-distribution`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return notFound("Business not found.", "business_not_found");
  if (business.user_id !== user.id) return apiError("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateResearchDistributionChannelBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: UpdateResearchDistributionChannelInput = {
    id: body.id,
    business_id: id,
    ...(body.channel !== undefined && { channel: body.channel }),
    ...(body.description !== undefined && { description: body.description }),
    ...(body.speed_score !== undefined && { speed_score: body.speed_score }),
    ...(body.cost_score !== undefined && { cost_score: body.cost_score }),
    ...(body.difficulty_score !== undefined && { difficulty_score: body.difficulty_score }),
    ...(body.reasoning !== undefined && { reasoning: body.reasoning }),
    ...(body.confidence !== undefined && { confidence: body.confidence }),
    ...(body.priority !== undefined && { priority: body.priority }),
  };

  const result = await updateResearchDistributionChannel(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return apiError(result.error ?? "Could not update distribution channel.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
