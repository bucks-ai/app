// GET  /api/businesses/[id]/validation   — return full validation workspace
// POST /api/businesses/[id]/validation   — seed workspace from blueprint

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import {
  getValidationWorkspace,
  seedValidationWorkspaceFromBlueprint,
} from "@/lib/validation";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// GET /api/businesses/[id]/validation
// ---------------------------------------------------------------------------

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return errorResponse("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { id } = await params;
  if (!id) return errorResponse("Business id is required.", "invalid_input", 400);

  const { user, response } = await requireUser();
  if (!user) return response;

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }

  if (businessResult.data.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  const result = await getValidationWorkspace(id);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_error";
    const httpStatus = code === "validation_schema_missing" ? 503 : 500;
    return errorResponse(
      result.error ?? "Could not load validation workspace.",
      code,
      httpStatus
    );
  }

  return Response.json({ ok: true, data: result.data });
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/validation
// Body: { action: "seed" }
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

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }

  if (businessResult.data.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  let body: Record<string, unknown> = {};
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse("Invalid JSON body.", "invalid_input", 400);
  }

  if (body.action !== "seed") {
    return errorResponse(
      'Unknown action. Supported actions: "seed".',
      "invalid_input",
      400
    );
  }

  const result = await seedValidationWorkspaceFromBlueprint(id);

  if (result.error || !result.data) {
    const code = result.code ?? "seed_failed";
    const httpStatus = code === "validation_schema_missing" ? 503 : 500;
    return errorResponse(
      result.error ?? "Could not seed validation workspace.",
      code,
      httpStatus
    );
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}
