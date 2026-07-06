// POST  /api/businesses/[id]/validation/leads   — create lead
// PATCH /api/businesses/[id]/validation/leads   — update lead (body must include id)

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import { createValidationLead, updateValidationLead } from "@/lib/validation";
import type {
  NewValidationLeadInput,
  UpdateValidationLeadInput,
} from "@/types/validation";
import { badRequest, zodIssuesToFields } from "@/lib/api-error";
import {
  createValidationLeadBodySchema,
  updateValidationLeadBodySchema,
} from "@/lib/schemas/validation";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

async function resolveBusiness(id: string) {
  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) return null;
  return businessResult.data;
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

  const { user, response } = await requireUser();
  if (!user) return response;

  const business = await resolveBusiness(id);
  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = createValidationLeadBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: NewValidationLeadInput = {
    business_id: id,
    user_id: user.id,
    name: body.name,
    company: body.company ?? null,
    role: body.role ?? null,
    segment: body.segment ?? null,
    source: body.source ?? "manual",
    contact_url: body.contact_url ?? null,
    email: body.email ?? null,
    status: body.status ?? "identified",
    notes: body.notes ?? null,
    priority: body.priority ?? "medium",
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

  const { user, response } = await requireUser();
  if (!user) return response;

  const business = await resolveBusiness(id);
  if (!business) return errorResponse("Business not found.", "business_not_found", 404);
  if (business.user_id !== user.id) return errorResponse("Access denied.", "forbidden", 403);

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = updateValidationLeadBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }
  const body = parsed.data;

  const input: UpdateValidationLeadInput = {
    id: body.id,
    business_id: id,
    ...(body.name !== undefined && { name: body.name }),
    ...(body.company !== undefined && { company: body.company }),
    ...(body.role !== undefined && { role: body.role }),
    ...(body.segment !== undefined && { segment: body.segment }),
    ...(body.source !== undefined && { source: body.source }),
    ...(body.contact_url !== undefined && { contact_url: body.contact_url }),
    ...(body.email !== undefined && { email: body.email }),
    ...(body.status !== undefined && { status: body.status }),
    ...(body.notes !== undefined && { notes: body.notes }),
    ...(body.priority !== undefined && { priority: body.priority }),
  };

  const result = await updateValidationLead(input);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_update_failed";
    return errorResponse(result.error ?? "Could not update lead.", code,
      code === "validation_schema_missing" ? 503 : 500);
  }

  return Response.json({ ok: true, data: result.data });
}
