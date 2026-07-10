// Server-side data helpers for the Execute button
// (POST /api/businesses/[id]/execute). Mirrors the conventions in
// src/lib/projects.ts. All functions are server-only.
//
// CRITICAL SAFETY: createMissionFromBlueprint always inserts
// runner_target: "business", never "self" — missions created from the app
// for a customer business must stay outside what the runner-side claim gate
// (runner/langgraph/tools/seeded_mission_queue.py) will pick up, until M4b
// lands per-business sandboxing. See
// supabase/migrations/0003_missions_runner_target.sql.

import { createSupabaseServerClient } from "@/lib/supabase/server";
import { compileBlueprintToMissionTasks, slug } from "@/lib/mission-compiler";
import type {
  MissionRecord,
  MissionTaskRecord,
  NewMissionInput,
  NewMissionTaskInput,
} from "@/types/database";

type Result<T> =
  | { data: T; error: null; code?: undefined }
  | { data: null; error: string; code?: string };

function ok<T>(data: T): Result<T> {
  return { data, error: null };
}

function err<T>(message: string, code?: string): Result<T> {
  return { data: null, error: message, code };
}

const NO_CLIENT =
  "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local.";

export interface CreateMissionInput {
  businessId: string;
  userId: string;
  businessName: string;
  blueprint: Record<string, unknown>;
}

export interface CreateMissionResult {
  mission: MissionRecord;
  tasks: MissionTaskRecord[];
}

/**
 * Compiles a business's saved blueprint into a mission and inserts the
 * missions + mission_tasks rows. Always business-targeted
 * (runner_target: "business") — the app never creates self-targeted
 * missions; only the runner's own dev/ops seed files do.
 */
export async function createMissionFromBlueprint(
  input: CreateMissionInput
): Promise<Result<CreateMissionResult>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const missionSlug = slug(input.businessName || "business", 30);
  let compiledTasks;
  try {
    compiledTasks = compileBlueprintToMissionTasks(input.blueprint, missionSlug);
  } catch (error) {
    return err(
      error instanceof Error ? error.message : "Failed to compile blueprint into tasks.",
      "compile_failed"
    );
  }

  const missionInsert: NewMissionInput = {
    business_id: input.businessId,
    user_id: input.userId,
    name: `Execute: ${input.businessName}`,
    goal: "Launch the first starter tasks compiled from the saved blueprint.",
    status: "queued",
    runner_target: "business",
    task_count: compiledTasks.length,
  };

  const { data: mission, error: missionError } = await supabase
    .from("missions")
    .insert(missionInsert as unknown as Record<string, unknown>)
    .select()
    .single();

  if (missionError) return err(missionError.message, "mission_create_failed");
  if (!mission) return err("Failed to create mission.", "mission_create_failed");

  const missionRow = mission as MissionRecord;

  const taskInserts: NewMissionTaskInput[] = compiledTasks.map((task) => ({
    mission_id: missionRow.id,
    business_id: input.businessId,
    user_id: input.userId,
    task_id: task.taskId,
    title: task.title,
    description: task.description,
    type: task.type,
    branch: task.branch,
    position: task.position,
    status: "queued",
  }));

  const { data: tasks, error: tasksError } = await supabase
    .from("mission_tasks")
    .insert(taskInserts as unknown as Record<string, unknown>[])
    .select();

  if (tasksError || !tasks) {
    // Best-effort cleanup so a failed task insert doesn't leave an orphaned,
    // task-less mission row visible in the UI.
    await supabase.from("missions").delete().eq("id", missionRow.id);
    return err(tasksError?.message ?? "Failed to create mission tasks.", "mission_tasks_create_failed");
  }

  return ok({ mission: missionRow, tasks: tasks as MissionTaskRecord[] });
}

export async function getMissionsForBusiness(
  businessId: string
): Promise<Result<MissionRecord[]>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const { data, error } = await supabase
    .from("missions")
    .select("*")
    .eq("business_id", businessId)
    .order("created_at", { ascending: false });

  if (error) return err(error.message, "missions_fetch_failed");
  return ok((data ?? []) as MissionRecord[]);
}

export async function getLatestMissionForBusiness(
  businessId: string
): Promise<Result<MissionRecord | null>> {
  const result = await getMissionsForBusiness(businessId);
  if (result.error || !result.data) {
    return err(result.error ?? "Failed to load missions.", "missions_fetch_failed");
  }
  return ok(result.data[0] ?? null);
}
