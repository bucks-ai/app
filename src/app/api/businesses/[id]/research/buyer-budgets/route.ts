// POST  /api/businesses/[id]/research/buyer-budgets   — create buyer budget record
// PATCH /api/businesses/[id]/research/buyer-budgets   — update record (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import {
  createResearchBuyerBudget,
  updateResearchBuyerBudget,
} from "@/lib/research";
import type {
  NewResearchBuyerBudgetInput,
  UpdateResearchBuyerBudgetInput,
} from "@/types/research";
import { apiError, unauthorized, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import {
  createResearchBuyerBudgetBodySchema,
  updateResearchBuyerBudgetBodySchema,
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

  const rateLimitResult = await limit(`${user.id}:research-buyer-budgets`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return notFound("Business not found.", "business_not_found");
  if (business.user_id !== user.id) return apiError("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createResearchBuyerBudgetBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewResearchBuyerBudgetInput = {
    business_id: id,
    user_id: user.id,
    buyer: body.buyer,
    budget_owner: body.budget_owner ?? null,
    existing_spend: body.existing_spend ?? null,
    willingness_to_pay: body.willingness_to_pay ?? null,
    value_driver: body.value_driver ?? null,
    pricing_signal: body.pricing_signal ?? null,
    confidence: body.confidence ?? null,
    priority: body.priority ?? "medium",
  };

  const result = await createResearchBuyerBudget(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_create_failed";
    return apiError(result.error ?? "Could not create buyer budget record.", code,
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

  const rateLimitResult = await limit(`${user.id}:research-buyer-budgets`, RATE_LIMITS.mutationDefault);
  if (!rateLimitResult.allowed) return tooManyRequests();

  if (!business) return notFound("Business not found.", "business_not_found");
  if (business.user_id !== user.id) return apiError("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateResearchBuyerBudgetBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: UpdateResearchBuyerBudgetInput = {
    id: body.id,
    business_id: id,
    ...(body.buyer !== undefined && { buyer: body.buyer }),
    ...(body.budget_owner !== undefined && { budget_owner: body.budget_owner }),
    ...(body.existing_spend !== undefined && { existing_spend: body.existing_spend }),
    ...(body.willingness_to_pay !== undefined && { willingness_to_pay: body.willingness_to_pay }),
    ...(body.value_driver !== undefined && { value_driver: body.value_driver }),
    ...(body.pricing_signal !== undefined && { pricing_signal: body.pricing_signal }),
    ...(body.confidence !== undefined && { confidence: body.confidence }),
    ...(body.priority !== undefined && { priority: body.priority }),
  };

  const result = await updateResearchBuyerBudget(input);

  if (result.error || !result.data) {
    const code = result.code ?? "research_update_failed";
    return apiError(result.error ?? "Could not update buyer budget record.", code,
      code === "research_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
