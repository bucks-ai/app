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
  ResearchConfidence,
  ResearchPriority,
} from "@/types/research";

const VALID_CONFIDENCES = new Set<ResearchConfidence>([
  "assumption", "weak_signal", "medium_signal", "strong_signal", "validated", "invalidated",
]);
const VALID_PRIORITIES = new Set<ResearchPriority>(["high", "medium", "low"]);
const VALID_CATEGORIES = new Set(["direct", "indirect", "substitute", "emerging"]);

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

  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (!name) return errorResponse("name is required.", "invalid_input", 400);

  const rawCategory = body.category as string | undefined;
  const rawConfidence = body.confidence as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: NewResearchCompetitorInput = {
    business_id: id,
    user_id: user.id,
    name,
    url: (body.url as string | null) ?? null,
    category: rawCategory && VALID_CATEGORIES.has(rawCategory) ? rawCategory : null,
    positioning: (body.positioning as string | null) ?? null,
    pricing_summary: (body.pricing_summary as string | null) ?? null,
    strengths: Array.isArray(body.strengths) ? (body.strengths as string[]) : null,
    weaknesses: Array.isArray(body.weaknesses) ? (body.weaknesses as string[]) : null,
    wedge_opportunity: (body.wedge_opportunity as string | null) ?? null,
    confidence: VALID_CONFIDENCES.has(rawConfidence as ResearchConfidence)
      ? (rawConfidence as ResearchConfidence)
      : null,
    priority: VALID_PRIORITIES.has(rawPriority as ResearchPriority)
      ? (rawPriority as ResearchPriority)
      : "medium",
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
  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let body: Record<string, unknown> = {};
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse("Invalid JSON body.", "invalid_input", 400);
  }

  const competitorId = typeof body.id === "string" ? body.id.trim() : "";
  if (!competitorId) return errorResponse("id (competitor uuid) is required.", "invalid_input", 400);

  const rawCategory = body.category as string | undefined;
  const rawConfidence = body.confidence as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: UpdateResearchCompetitorInput = {
    id: competitorId,
    business_id: id,
    ...(body.name !== undefined && { name: body.name as string }),
    ...(body.url !== undefined && { url: body.url as string | null }),
    ...(rawCategory !== undefined && {
      category: VALID_CATEGORIES.has(rawCategory) ? rawCategory : null,
    }),
    ...(body.positioning !== undefined && { positioning: body.positioning as string | null }),
    ...(body.pricing_summary !== undefined && { pricing_summary: body.pricing_summary as string | null }),
    ...(body.strengths !== undefined && {
      strengths: Array.isArray(body.strengths) ? (body.strengths as string[]) : null,
    }),
    ...(body.weaknesses !== undefined && {
      weaknesses: Array.isArray(body.weaknesses) ? (body.weaknesses as string[]) : null,
    }),
    ...(body.wedge_opportunity !== undefined && { wedge_opportunity: body.wedge_opportunity as string | null }),
    ...(rawConfidence !== undefined &&
      VALID_CONFIDENCES.has(rawConfidence as ResearchConfidence) && {
        confidence: rawConfidence as ResearchConfidence,
      }),
    ...(rawPriority !== undefined &&
      VALID_PRIORITIES.has(rawPriority as ResearchPriority) && {
        priority: rawPriority as ResearchPriority,
      }),
  };

  const result = await updateResearchCompetitor(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return errorResponse(result.error ?? "Could not update competitor.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
