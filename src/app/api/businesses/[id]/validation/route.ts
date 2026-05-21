import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import {
  getValidationWorkspace,
  seedValidationWorkspaceFromBlueprint,
} from "@/lib/validation";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// GET /api/businesses/[id]/validation
// Returns the full validation workspace. If empty, includes canSeed: true.
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

  const result = await getValidationWorkspace(id);

  if (result.error || !result.data) {
    const code = result.code ?? "validation_error";
    if (code === "validation_schema_missing") {
      return errorResponse(result.error ?? "Validation schema missing.", code, 503);
    }
    return errorResponse(result.error ?? "Could not load validation workspace.", code, 500);
  }

  return Response.json({ ok: true, data: result.data });
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/validation
// Body: { action: "seed" }
// Seeds the validation workspace from the latest blueprint.
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

  if (body.action !== "seed") {
    return errorResponse(
      "Unknown action. Supported: seed.",
      "invalid_action",
      400
    );
  }

  const result = await seedValidationWorkspaceFromBlueprint(id);

  if (result.error || !result.data) {
    const code = result.code ?? "seed_error";
    if (code === "validation_schema_missing") {
      return errorResponse(result.error ?? "Validation schema missing.", code, 503);
    }
    return errorResponse(result.error ?? "Could not seed validation workspace.", code, 500);
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}
