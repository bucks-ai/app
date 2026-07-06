// GET  /api/businesses/[id]/research   — return full research workspace
// POST /api/businesses/[id]/research   — generate workspace from blueprint

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import {
  getResearchWorkspace,
  generateResearchWorkspaceFromBlueprint,
} from "@/lib/research";
import { badRequest, zodIssuesToFields } from "@/lib/api-error";
import { generateResearchBodySchema } from "@/lib/schemas/research";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// GET /api/businesses/[id]/research
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
    return errorResponse("Business not found.", "business_not_found", 404);
  }

  if (businessResult.data.user_id !== userResult.data.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  const result = await getResearchWorkspace(id);

  if (result.error || !result.data) {
    const code = result.code ?? "research_error";
    const httpStatus = code === "research_schema_missing" ? 503 : 500;
    return errorResponse(
      result.error ?? "Could not load research workspace.",
      code,
      httpStatus
    );
  }

  return Response.json({ ok: true, data: result.data });
}

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/research
// Body: { action: "generate" }
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

  const rateLimitResult = await limit(
    `${userResult.data.id}:research-generate`,
    RATE_LIMITS.researchGenerate,
  );
  if (!rateLimitResult.allowed) return tooManyRequests();

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }

  if (businessResult.data.user_id !== userResult.data.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = generateResearchBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const result = await generateResearchWorkspaceFromBlueprint(id);

  if (result.error || !result.data) {
    const code = result.code ?? "research_generate_failed";
    const httpStatus = code === "research_schema_missing" ? 503 : 500;
    return errorResponse(
      result.error ?? "Could not generate research workspace.",
      code,
      httpStatus
    );
  }

  return Response.json({ ok: true, data: result.data }, { status: 201 });
}
