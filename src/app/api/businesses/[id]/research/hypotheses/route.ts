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
} from "@/types/research";
import { apiError, unauthorized, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import {
  createResearchHypothesisBodySchema,
  updateResearchHypothesisBodySchema,
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

  const rateLimitResult = await limit(`${user.id}:research-hypotheses`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return notFound("Business not found.", "business_not_found");
  if (business.user_id !== user.id) return apiError("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createResearchHypothesisBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewResearchHypothesisInput = {
    business_id: id,
    user_id: user.id,
    title: body.title,
    description: body.description ?? null,
    test_method: body.test_method ?? null,
    success_criteria: body.success_criteria ?? null,
    confidence: body.confidence ?? null,
    priority: body.priority ?? "medium",
  };

  const result = await createResearchHypothesis(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return apiError(result.error ?? "Could not create research hypothesis.", code,
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

  const rateLimitResult = await limit(`${user.id}:research-hypotheses`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return notFound("Business not found.", "business_not_found");
  if (business.user_id !== user.id) return apiError("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateResearchHypothesisBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: UpdateResearchHypothesisInput = {
    id: body.id,
    business_id: id,
    ...(body.title !== undefined && { title: body.title }),
    ...(body.description !== undefined && { description: body.description }),
    ...(body.test_method !== undefined && { test_method: body.test_method }),
    ...(body.success_criteria !== undefined && { success_criteria: body.success_criteria }),
    ...(body.confidence !== undefined && { confidence: body.confidence }),
    ...(body.priority !== undefined && { priority: body.priority }),
  };

  const result = await updateResearchHypothesis(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return apiError(result.error ?? "Could not update research hypothesis.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
