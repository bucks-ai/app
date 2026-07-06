import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById } from "@/lib/projects";
import { requireUser } from "@/lib/api-auth";
import {
  getToolPermissionsForBusiness,
  seedToolPermissionsForBusiness,
  createToolPermissionActivityLog,
} from "@/lib/tool-permissions";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// GET /api/tool-permissions?businessId=...
// Returns tool permissions for the business. Does NOT auto-seed.
// Returns canSeed: true when no records exist yet.
// ---------------------------------------------------------------------------

export async function GET(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return errorResponse(
      "Supabase is not configured.",
      "missing_supabase_env",
      503
    );
  }

  const { searchParams } = new URL(request.url);
  const businessId = searchParams.get("businessId");

  if (!businessId) {
    return errorResponse("businessId query parameter is required.", "invalid_input", 400);
  }

  const { user, response } = await requireUser();
  if (!user) return response;

  // Verify ownership
  const businessResult = await getBusinessById(businessId);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "not_found", 404);
  }
  if (businessResult.data.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  const result = await getToolPermissionsForBusiness(businessId);
  if (result.error) {
    return errorResponse(result.error, "not_found", 500);
  }

  const permissions = result.data ?? [];

  return Response.json({
    ok: true,
    data: {
      permissions,
      canSeed: permissions.length === 0,
    },
  });
}

// ---------------------------------------------------------------------------
// POST /api/tool-permissions
// Seeds default tool permissions for a business. Idempotent.
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return errorResponse(
      "Supabase is not configured.",
      "missing_supabase_env",
      503
    );
  }

  let body: { businessId?: string };
  try {
    body = (await request.json()) as { businessId?: string };
  } catch {
    return errorResponse("Request body must be valid JSON.", "invalid_input", 400);
  }

  const { businessId } = body;
  if (!businessId || typeof businessId !== "string") {
    return errorResponse("businessId is required in the request body.", "invalid_input", 400);
  }

  const { user, response } = await requireUser();
  if (!user) return response;

  // Verify ownership
  const businessResult = await getBusinessById(businessId);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "not_found", 404);
  }
  if (businessResult.data.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  const seedResult = await seedToolPermissionsForBusiness(businessId, user.id);
  if (seedResult.error || !seedResult.data) {
    return errorResponse(
      seedResult.error ?? "Seed failed.",
      "seed_failed",
      500
    );
  }

  if (seedResult.data.seeded > 0) {
    await createToolPermissionActivityLog({
      business_id: businessId,
      user_id: user.id,
      activity_type: "tool_permissions_seeded",
      message: `Created initial tool permission setup queue. ${seedResult.data.seeded} tools added.`,
      metadata: {
        seeded: seedResult.data.seeded,
        skipped: seedResult.data.skipped,
      },
    });
  }

  return Response.json({
    ok: true,
    data: seedResult.data,
  });
}
