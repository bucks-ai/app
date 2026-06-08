import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { evaluateDeploymentGate } from "@/lib/vercel/deploy-gate";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

// ---------------------------------------------------------------------------
// GET /api/vercel/deploy-gate?businessId=...
//
// Returns a pass/blocked verdict on whether the business's Vercel deployment is
// ready enough to permit deploy-dependent actions (e.g. customer validation
// against a live URL). The gate decision is always returned with HTTP 200 in
// `data`; non-200s are reserved for auth/ownership/input failures.
// ---------------------------------------------------------------------------

export async function GET(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return errorResponse("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { searchParams } = new URL(request.url);
  const businessId = searchParams.get("businessId");
  if (!businessId) {
    return errorResponse("businessId query param is required.", "invalid_input", 400);
  }

  // Auth
  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return errorResponse("Authentication required.", "unauthenticated", 401);
  }
  const user = userResult.data;

  // Business ownership
  const businessResult = await getBusinessById(businessId);
  if (businessResult.error || !businessResult.data) {
    return errorResponse("Business not found.", "business_not_found", 404);
  }
  if (businessResult.data.user_id !== user.id) {
    return errorResponse("Access denied.", "forbidden", 403);
  }

  const gate = await evaluateDeploymentGate(businessId);

  return Response.json({ ok: true, data: gate });
}
