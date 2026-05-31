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

  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (!name) return errorResponse("name is required.", "invalid_input", 400);

  const rawConfidence = body.confidence as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: NewResearchCustomerSegmentInput = {
    business_id: id,
    user_id: user.id,
    name,
    description: (body.description as string | null) ?? null,
    pain_level:
      typeof body.pain_level === "number" && body.pain_level >= 0 && body.pain_level <= 10
        ? body.pain_level
        : null,
    ability_to_pay:
      typeof body.ability_to_pay === "number" && body.ability_to_pay >= 0 && body.ability_to_pay <= 10
        ? body.ability_to_pay
        : null,
    reachability:
      typeof body.reachability === "number" && body.reachability >= 0 && body.reachability <= 10
        ? body.reachability
        : null,
    market_size_guess: (body.market_size_guess as string | null) ?? null,
    channels: Array.isArray(body.channels) ? (body.channels as string[]) : null,
    evidence_summary: (body.evidence_summary as string | null) ?? null,
    confidence: VALID_CONFIDENCES.has(rawConfidence as ResearchConfidence)
      ? (rawConfidence as ResearchConfidence)
      : null,
    priority: VALID_PRIORITIES.has(rawPriority as ResearchPriority)
      ? (rawPriority as ResearchPriority)
      : "medium",
  };

  const result = await createResearchCustomerSegment(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return errorResponse(result.error ?? "Could not create segment.", code,
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

  const segmentId = typeof body.id === "string" ? body.id.trim() : "";
  if (!segmentId) return errorResponse("id (segment uuid) is required.", "invalid_input", 400);

  const rawConfidence = body.confidence as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: UpdateResearchCustomerSegmentInput = {
    id: segmentId,
    business_id: id,
    ...(body.name !== undefined && { name: body.name as string }),
    ...(body.description !== undefined && { description: body.description as string | null }),
    ...(body.pain_level !== undefined && {
      pain_level:
        typeof body.pain_level === "number" && body.pain_level >= 0 && body.pain_level <= 10
          ? body.pain_level
          : null,
    }),
    ...(body.ability_to_pay !== undefined && {
      ability_to_pay:
        typeof body.ability_to_pay === "number" && body.ability_to_pay >= 0 && body.ability_to_pay <= 10
          ? body.ability_to_pay
          : null,
    }),
    ...(body.reachability !== undefined && {
      reachability:
        typeof body.reachability === "number" && body.reachability >= 0 && body.reachability <= 10
          ? body.reachability
          : null,
    }),
    ...(body.market_size_guess !== undefined && { market_size_guess: body.market_size_guess as string | null }),
    ...(body.channels !== undefined && {
      channels: Array.isArray(body.channels) ? (body.channels as string[]) : null,
    }),
    ...(body.evidence_summary !== undefined && { evidence_summary: body.evidence_summary as string | null }),
    ...(rawConfidence !== undefined &&
      VALID_CONFIDENCES.has(rawConfidence as ResearchConfidence) && {
        confidence: rawConfidence as ResearchConfidence,
      }),
    ...(rawPriority !== undefined &&
      VALID_PRIORITIES.has(rawPriority as ResearchPriority) && {
        priority: rawPriority as ResearchPriority,
      }),
  };

  const result = await updateResearchCustomerSegment(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return errorResponse(result.error ?? "Could not update segment.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
