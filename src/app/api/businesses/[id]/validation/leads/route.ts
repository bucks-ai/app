import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { createValidationLead, updateValidationLead } from "@/lib/validation";
import type {
  NewValidationLeadInput,
  UpdateValidationLeadInput,
  ValidationLeadStatus,
  ValidationSource,
} from "@/types/validation";

const VALID_LEAD_STATUSES = new Set<ValidationLeadStatus>([
  "identified",
  "contacted",
  "replied",
  "scheduled",
  "interviewed",
  "not_interested",
]);

const VALID_SOURCES = new Set<ValidationSource>([
  "manual",
  "blueprint",
  "linkedin",
  "twitter",
  "email",
  "referral",
  "other",
]);

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/validation/leads
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

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return errorResponse("Authentication required.", "unauthenticated", 401);
  }

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "not_found", 404);
  }

  if (businessResult.data.user_id !== userResult.data.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  let body: Record<string, unknown> = {};
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse("Invalid JSON body.", "invalid_input", 400);
  }

  const name = body.name as string | undefined;
  if (!name?.trim()) {
    return errorResponse("name is required.", "invalid_input", 400);
  }

  const rawStatus = body.status as string | undefined;
  const rawSource = body.source as string | undefined;

  const input: NewValidationLeadInput = {
    business_id: id,
    user_id: userResult.data.id,
    name: name.trim(),
    company: (body.company as string | null) ?? null,
    role: (body.role as string | null) ?? null,
    contact_info: (body.contact_info as string | null) ?? null,
    source:
      rawSource && VALID_SOURCES.has(rawSource as ValidationSource)
        ? (rawSource as ValidationSource)
        : "manual",
    status:
      rawStatus && VALID_LEAD_STATUSES.has(rawStatus as ValidationLeadStatus)
        ? (rawStatus as ValidationLeadStatus)
        : "identified",
    persona_id: (body.persona_id as string | null) ?? null,
    notes: (body.notes as string | null) ?? null,
    outreach_script: (body.outreach_script as string | null) ?? null,
  };

  const result = await createValidationLead(input);

  if (result.error || !result.data) {
    const code = result.code ?? "create_error";
    if (code === "validation_schema_missing") {
      return errorResponse(result.error ?? "Validation schema missing.", code, 503);
    }
    return errorResponse(result.error ?? "Could not create lead.", code, 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}

// ---------------------------------------------------------------------------
// PATCH /api/businesses/[id]/validation/leads
// Body: UpdateValidationLeadInput (must include id)
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

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return errorResponse("Authentication required.", "unauthenticated", 401);
  }

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "not_found", 404);
  }

  if (businessResult.data.user_id !== userResult.data.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  let body: Record<string, unknown> = {};
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse("Invalid JSON body.", "invalid_input", 400);
  }

  const leadId = body.id as string | undefined;
  if (!leadId?.trim()) {
    return errorResponse("id is required.", "invalid_input", 400);
  }

  const rawStatus = body.status as string | undefined;
  const rawSource = body.source as string | undefined;

  const input: UpdateValidationLeadInput = {
    id: leadId.trim(),
    business_id: id,
    ...(body.name !== undefined && { name: body.name as string }),
    ...(body.company !== undefined && { company: body.company as string | null }),
    ...(body.role !== undefined && { role: body.role as string | null }),
    ...(body.contact_info !== undefined && {
      contact_info: body.contact_info as string | null,
    }),
    ...(rawSource !== undefined &&
      VALID_SOURCES.has(rawSource as ValidationSource) && {
        source: rawSource as ValidationSource,
      }),
    ...(rawStatus !== undefined &&
      VALID_LEAD_STATUSES.has(rawStatus as ValidationLeadStatus) && {
        status: rawStatus as ValidationLeadStatus,
      }),
    ...(body.persona_id !== undefined && { persona_id: body.persona_id as string | null }),
    ...(body.notes !== undefined && { notes: body.notes as string | null }),
    ...(body.outreach_script !== undefined && {
      outreach_script: body.outreach_script as string | null,
    }),
  };

  const result = await updateValidationLead(input);

  if (result.error || !result.data) {
    const code = result.code ?? "update_error";
    if (code === "validation_schema_missing") {
      return errorResponse(result.error ?? "Validation schema missing.", code, 503);
    }
    return errorResponse(result.error ?? "Could not update lead.", code, 500);
  }

  return Response.json({ ok: true, data: result.data });
}
