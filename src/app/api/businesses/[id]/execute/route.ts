// POST /api/businesses/[id]/execute
// The pivot MVP Execute button: compiles the business's saved blueprint into
// a mission (missions row + mission_tasks rows) with a small deterministic
// compiler (src/lib/mission-compiler.ts) — no LLM call in this route.
//
// CRITICAL SAFETY: every mission created here is runner_target: "business"
// (src/lib/missions.ts::createMissionFromBlueprint). The runner's claim gate
// (runner/langgraph/tools/seeded_mission_queue.py::fetch_next_queued_mission)
// only ever claims runner_target: "self" missions, so a mission created here
// sits visibly queued and is never executed against the bucks-ai repo until
// M4b lands per-business sandboxing.
//
// GET /api/businesses/[id]/execute
// Returns the business's most recent mission (or null) so the UI can show
// queued/running/completed status without re-triggering compilation.
//
// Response shapes:
//   success: { ok: true, data: { mission: MissionRecord, tasks: MissionTaskRecord[] } }  (POST)
//            { ok: true, data: { mission: MissionRecord | null } }                       (GET)
//   error:   { ok: false, code: string, error: string }
//
// Error codes:
//   unauthenticated            — no session
//   forbidden                  — wrong owner
//   business_not_found         — business does not exist
//   blueprint_not_found        — business has no saved blueprint to compile
//   compile_failed             — blueprint could not be compiled into tasks
//   mission_create_failed      — missions insert failed
//   mission_tasks_create_failed — mission_tasks insert failed
//   missions_fetch_failed      — GET could not load missions

import { hasSupabaseEnv } from "@/lib/supabase/env";
import { getBusinessById, getLatestBlueprintForBusiness } from "@/lib/projects";
import { createMissionFromBlueprint, getLatestMissionForBusiness } from "@/lib/missions";
import { requireUser } from "@/lib/api-auth";
import { apiError, badRequest, notFound, zodIssuesToFields } from "@/lib/api-error";
import { executeBusinessParamsSchema } from "@/lib/schemas/infra";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";

async function resolveOwnedBusiness(id: string, userId: string) {
  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return { error: notFound("Business not found.", "business_not_found") };
  }
  if (businessResult.data.user_id !== userId) {
    return { error: apiError("Access denied.", "forbidden", 403) };
  }
  return { business: businessResult.data };
}

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const rawParams = await params;
  const parsed = executeBusinessParamsSchema.safeParse(rawParams);
  if (!parsed.success) {
    return badRequest(
      "Request path failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const { id } = parsed.data;

  const { user, response } = await requireUser();
  if (!user) return response;

  const rateLimitResult = await limit(`${user.id}:execute-business`, RATE_LIMITS.executeBusiness);
  if (!rateLimitResult.allowed) return tooManyRequests();

  const owned = await resolveOwnedBusiness(id, user.id);
  if (owned.error) return owned.error;
  const business = owned.business;

  const blueprintResult = await getLatestBlueprintForBusiness(id);
  if (blueprintResult.error || !blueprintResult.data) {
    return notFound(
      "This business has no saved blueprint to compile into a mission.",
      "blueprint_not_found",
    );
  }

  const result = await createMissionFromBlueprint({
    businessId: id,
    userId: user.id,
    businessName: business.idea_name,
    blueprint: blueprintResult.data.blueprint,
  });

  if (result.error || !result.data) {
    const code = result.code ?? "mission_create_failed";
    return apiError(result.error ?? "Could not create mission.", code, 500);
  }

  return Response.json({ ok: true, data: result.data });
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!hasSupabaseEnv()) {
    return apiError("Supabase is not configured.", "missing_supabase_env", 503);
  }

  const rawParams = await params;
  const parsed = executeBusinessParamsSchema.safeParse(rawParams);
  if (!parsed.success) {
    return badRequest(
      "Request path failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const { id } = parsed.data;

  const { user, response } = await requireUser();
  if (!user) return response;

  const owned = await resolveOwnedBusiness(id, user.id);
  if (owned.error) return owned.error;

  const missionResult = await getLatestMissionForBusiness(id);
  if (missionResult.error) {
    return apiError(missionResult.error, "missions_fetch_failed", 500);
  }

  return Response.json({ ok: true, data: { mission: missionResult.data } });
}
