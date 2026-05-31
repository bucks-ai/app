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
  ResearchConfidence,
  ResearchPriority,
} from "@/types/research";

const VALID_CONFIDENCES = new Set<ResearchConfidence>([
  "assumption", "weak_signal", "medium_signal", "strong_signal", "validated", "invalidated",
]);
const VALID_PRIORITIES = new Set<ResearchPriority>(["high", "medium", "low"]);

function safeScore(v: unknown): number | null {
  return typeof v === "number" && v >= 0 && v <= 10 ? v : null;
}

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

  const channel = typeof body.channel === "string" ? body.channel.trim() : "";
  if (!channel) return errorResponse("channel is required.", "invalid_input", 400);

  const rawConfidence = body.confidence as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: NewResearchDistributionChannelInput = {
    business_id: id,
    user_id: user.id,
    channel,
    description: (body.description as string | null) ?? null,
    speed_score: safeScore(body.speed_score),
    cost_score: safeScore(body.cost_score),
    difficulty_score: safeScore(body.difficulty_score),
    reasoning: (body.reasoning as string | null) ?? null,
    confidence: VALID_CONFIDENCES.has(rawConfidence as ResearchConfidence)
      ? (rawConfidence as ResearchConfidence)
      : null,
    priority: VALID_PRIORITIES.has(rawPriority as ResearchPriority)
      ? (rawPriority as ResearchPriority)
      : "medium",
  };

  const result = await createResearchDistributionChannel(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return errorResponse(result.error ?? "Could not create distribution channel.", code,
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

  const channelId = typeof body.id === "string" ? body.id.trim() : "";
  if (!channelId) return errorResponse("id (channel uuid) is required.", "invalid_input", 400);

  const rawConfidence = body.confidence as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: UpdateResearchDistributionChannelInput = {
    id: channelId,
    business_id: id,
    ...(body.channel !== undefined && { channel: body.channel as string }),
    ...(body.description !== undefined && { description: body.description as string | null }),
    ...(body.speed_score !== undefined && { speed_score: safeScore(body.speed_score) }),
    ...(body.cost_score !== undefined && { cost_score: safeScore(body.cost_score) }),
    ...(body.difficulty_score !== undefined && { difficulty_score: safeScore(body.difficulty_score) }),
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

  const result = await updateResearchDistributionChannel(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return errorResponse(result.error ?? "Could not update distribution channel.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
