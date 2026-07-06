// POST  /api/businesses/[id]/research/competitors   — create competitor record
// PATCH /api/businesses/[id]/research/competitors   — update record (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import {
  createResearchCompetitor,
  updateResearchCompetitor,
} from "@/lib/research";
import type {
  NewResearchCompetitorInput,
  UpdateResearchCompetitorInput,
} from "@/types/research";
import { badRequest, zodIssuesToFields } from "@/lib/api-error";
import {
  createResearchCompetitorBodySchema,
  updateResearchCompetitorBodySchema,
} from "@/lib/schemas/research";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

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

  const rateLimitResult = await limit(`${user.id}:research-competitors`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createResearchCompetitorBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewResearchCompetitorInput = {
    business_id: id,
    user_id: user.id,
    name: body.name,
    url: body.url ?? null,
    category: body.category ?? null,
    positioning: body.positioning ?? null,
    pricing_summary: body.pricing_summary ?? null,
    strengths: body.strengths ?? null,
    weaknesses: body.weaknesses ?? null,
    wedge_opportunity: body.wedge_opportunity ?? null,
    confidence: body.confidence ?? null,
    priority: body.priority ?? "medium",
  };

  const result = await createResearchCompetitor(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return errorResponse(result.error ?? "Could not create competitor.", code,
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

  const rateLimitResult = await limit(`${user.id}:research-competitors`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateResearchCompetitorBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: UpdateResearchCompetitorInput = {
    id: body.id,
    business_id: id,
    ...(body.name !== undefined && { name: body.name }),
    ...(body.url !== undefined && { url: body.url }),
    ...(body.category !== undefined && { category: body.category }),
    ...(body.positioning !== undefined && { positioning: body.positioning }),
    ...(body.pricing_summary !== undefined && { pricing_summary: body.pricing_summary }),
    ...(body.strengths !== undefined && { strengths: body.strengths }),
    ...(body.weaknesses !== undefined && { weaknesses: body.weaknesses }),
    ...(body.wedge_opportunity !== undefined && { wedge_opportunity: body.wedge_opportunity }),
    ...(body.confidence !== undefined && { confidence: body.confidence }),
    ...(body.priority !== undefined && { priority: body.priority }),
  };

  const result = await updateResearchCompetitor(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return errorResponse(result.error ?? "Could not update competitor.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
