import { NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getCurrentUser, getBusinessById } from "@/lib/projects";
import { evaluateDeploymentGate } from "@/lib/vercel/deploy-gate";
import { apiError, unauthorized, badRequest, notFound } from "@/lib/api-error";

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
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const { searchParams } = new URL(request.url);
  const businessId = searchParams.get("businessId");
  if (!businessId) {
    return badRequest("businessId query param is required.", "invalid_input");
  }

  // Auth
  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return unauthorized();
  }
  const user = userResult.data;

  // Business ownership
  const businessResult = await getBusinessById(businessId);
  if (businessResult.error || !businessResult.data) {
    return notFound("Business not found.", "business_not_found");
  }
  if (businessResult.data.user_id !== user.id) {
    return apiError("Access denied.", "forbidden", 403);
  }

  const gate = await evaluateDeploymentGate(businessId);

  return Response.json({ ok: true, data: gate });
}
