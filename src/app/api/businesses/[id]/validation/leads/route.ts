// POST  /api/businesses/[id]/validation/leads   — create lead
// PATCH /api/businesses/[id]/validation/leads   — update lead (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { createValidationLead, updateValidationLead } from "@/lib/validation";
import type {
  NewValidationLeadInput,
  UpdateValidationLeadInput,
  ValidationLeadStatus,
  ValidationSource,
  ValidationPriority,
} from "@/types/validation";

const VALID_STATUSES = new Set<ValidationLeadStatus>([
  "identified", "contacted", "replied", "scheduled", "interviewed", "not_interested",
]);
const VALID_SOURCES = new Set<ValidationSource>([
  "manual", "blueprint", "linkedin", "twitter", "email", "referral", "other",
]);
const VALID_PRIORITIES = new Set<ValidationPriority>(["high", "medium", "low"]);

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

  const rawStatus = body.status as string | undefined;
  const rawSource = body.source as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: NewValidationLeadInput = {
    business_id: id,
    user_id: user.id,
    name,
    company: (body.company as string | null) ?? null,
    role: (body.role as string | null) ?? null,
    segment: (body.segment as string | null) ?? null,
    source: VALID_SOURCES.has(rawSource as ValidationSource)
      ? (rawSource as ValidationSource)
      : "manual",
    contact_url: (body.contact_url as string | null) ?? null,
    email: (body.email as string | null) ?? null,
    status: VALID_STATUSES.has(rawStatus as ValidationLeadStatus)
      ? (rawStatus as ValidationLeadStatus)
      : "identified",
    notes: (body.notes as string | null) ?? null,
    priority: VALID_PRIORITIES.has(rawPriority as ValidationPriority)
      ? (rawPriority as ValidationPriority)
      : "medium",
  };

  const result = await createValidationLead(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_create_failed";
    return errorResponse(result.error ?? "Could not create lead.", code,
      code === "validation_schema_missing" ? 503 : 500);
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

  const leadId = typeof body.id === "string" ? body.id.trim() : "";
  if (!leadId) return errorResponse("id (lead uuid) is required.", "invalid_input", 400);

  const rawStatus = body.status as string | undefined;
  const rawSource = body.source as string | undefined;
  const rawPriority = body.priority as string | undefined;

  const input: UpdateValidationLeadInput = {
    id: leadId,
    business_id: id,
    ...(body.name !== undefined && { name: body.name as string }),
    ...(body.company !== undefined && { company: body.company as string | null }),
    ...(body.role !== undefined && { role: body.role as string | null }),
    ...(body.segment !== undefined && { segment: body.segment as string | null }),
    ...(rawSource !== undefined &&
      VALID_SOURCES.has(rawSource as ValidationSource) && {
        source: rawSource as ValidationSource,
      }),
    ...(body.contact_url !== undefined && { contact_url: body.contact_url as string | null }),
    ...(body.email !== undefined && { email: body.email as string | null }),
    ...(rawStatus !== undefined &&
      VALID_STATUSES.has(rawStatus as ValidationLeadStatus) && {
        status: rawStatus as ValidationLeadStatus,
      }),
    ...(body.notes !== undefined && { notes: body.notes as string | null }),
    ...(rawPriority !== undefined &&
      VALID_PRIORITIES.has(rawPriority as ValidationPriority) && {
        priority: rawPriority as ValidationPriority,
      }),
  };

  const result = await updateValidationLead(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_update_failed";
    return errorResponse(result.error ?? "Could not update lead.", code,
      code === "validation_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
