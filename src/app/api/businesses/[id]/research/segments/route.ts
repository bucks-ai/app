// POST  /api/businesses/[id]/research/segments   — create customer segment
// PATCH /api/businesses/[id]/research/segments   — update segment (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import {
  createResearchCustomerSegment,
  updateResearchCustomerSegment,
} from "@/lib/research";
import type {
  NewResearchCustomerSegmentInput,
  UpdateResearchCustomerSegmentInput,
} from "@/types/research";
import { apiError, unauthorized, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import {
  createResearchSegmentBodySchema,
  updateResearchSegmentBodySchema,
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

  const rateLimitResult = await limit(`${user.id}:research-segments`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return notFound("Business not found.", "business_not_found");
  if (business.user_id !== user.id) return apiError("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createResearchSegmentBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewResearchCustomerSegmentInput = {
    business_id: id,
    user_id: user.id,
    name: body.name,
    description: body.description ?? null,
    pain_level: body.pain_level ?? null,
    ability_to_pay: body.ability_to_pay ?? null,
    reachability: body.reachability ?? null,
    market_size_guess: body.market_size_guess ?? null,
    channels: body.channels ?? null,
    evidence_summary: body.evidence_summary ?? null,
    confidence: body.confidence ?? null,
    priority: body.priority ?? "medium",
  };

  const result = await createResearchCustomerSegment(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return apiError(result.error ?? "Could not create segment.", code,
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

  const rateLimitResult = await limit(`${user.id}:research-segments`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return notFound("Business not found.", "business_not_found");
  if (business.user_id !== user.id) return apiError("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateResearchSegmentBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: UpdateResearchCustomerSegmentInput = {
    id: body.id,
    business_id: id,
    ...(body.name !== undefined && { name: body.name }),
    ...(body.description !== undefined && { description: body.description }),
    ...(body.pain_level !== undefined && { pain_level: body.pain_level }),
    ...(body.ability_to_pay !== undefined && { ability_to_pay: body.ability_to_pay }),
    ...(body.reachability !== undefined && { reachability: body.reachability }),
    ...(body.market_size_guess !== undefined && { market_size_guess: body.market_size_guess }),
    ...(body.channels !== undefined && { channels: body.channels }),
    ...(body.evidence_summary !== undefined && { evidence_summary: body.evidence_summary }),
    ...(body.confidence !== undefined && { confidence: body.confidence }),
    ...(body.priority !== undefined && { priority: body.priority }),
  };

  const result = await updateResearchCustomerSegment(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return apiError(result.error ?? "Could not update segment.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
