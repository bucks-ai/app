// Mission Queue — TypeScript types.
// A mission is a strategic unit of work compiled from a YAML file in the
// runner's inbox/. It groups an ordered set of runner tasks under a single goal.
//
// Mirrors the missions and mission_tasks tables in supabase/missions.sql.
// The runner task dict shape is defined in runner/langgraph/tools/task_tools.py.

// ---------------------------------------------------------------------------
// Mission status
// ---------------------------------------------------------------------------

export type MissionStatus =
  | "queued"     // all tasks waiting to start
  | "running"    // at least one task is active
  | "completed"  // all tasks finished successfully
  | "failed"     // one or more tasks failed and exhausted retries
  | "cancelled"; // manually cancelled before completion

// ---------------------------------------------------------------------------
// Mission task status — mirrors runner task_tools.py status values
// ---------------------------------------------------------------------------

export type MissionTaskStatus =
  | "queued"
  | "running"
  | "complete"
  | "failed"
  | "blocked";

// ---------------------------------------------------------------------------
// Task type — valid runner task types from mission_compiler.py
// ---------------------------------------------------------------------------

export type MissionTaskType =
  | "backend"
  | "design"
  | "docs"
  | "frontend"
  | "general"
  | "infra"
  | "polish"
  | "test"
  | "ui";

// ---------------------------------------------------------------------------
// Preferred worker — LLM workers available in the runner
// ---------------------------------------------------------------------------

export type MissionWorker = "codex" | "claude" | "chatgpt";

// ---------------------------------------------------------------------------
// Mission record — mirrors the missions table
// ---------------------------------------------------------------------------

export interface MissionRecord {
  id: string;
  business_id: string;
  user_id: string;
  name: string;
  goal: string | null;
  status: MissionStatus;
  source_file: string | null;
  task_count: number;
  completed_task_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Mission task record — mirrors the mission_tasks table
// ---------------------------------------------------------------------------

export interface MissionTaskRecord {
  id: string;
  mission_id: string;
  business_id: string;
  user_id: string;
  task_id: string;
  title: string;
  type: MissionTaskType;
  branch: string;
  preferred_worker: MissionWorker | null;
  position: number;
  status: MissionTaskStatus;
  summary: string | null;
  error: string | null;
  retry_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Mission with tasks — mission record + ordered task list
// ---------------------------------------------------------------------------

export interface MissionWithTasks extends MissionRecord {
  tasks: MissionTaskRecord[];
}

// ---------------------------------------------------------------------------
// Progress — computed view for a mission's task completion state
// ---------------------------------------------------------------------------

export interface MissionProgress {
  missionId: string;
  taskCount: number;
  completedCount: number;
  failedCount: number;
  runningCount: number;
  blockedCount: number;
  queuedCount: number;
  percentComplete: number;
}

// ---------------------------------------------------------------------------
// Create / update inputs
// ---------------------------------------------------------------------------

export interface MissionCreateInput {
  business_id: string;
  user_id: string;
  name: string;
  goal?: string | null;
  status?: MissionStatus;
  source_file?: string | null;
  task_count?: number;
}

export interface MissionUpdateInput {
  id: string;
  status?: MissionStatus;
  completed_task_count?: number;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface MissionTaskCreateInput {
  mission_id: string;
  business_id: string;
  user_id: string;
  task_id: string;
  title: string;
  type?: MissionTaskType;
  branch: string;
  preferred_worker?: MissionWorker | null;
  position: number;
  status?: MissionTaskStatus;
}

export interface MissionTaskUpdateInput {
  id: string;
  status?: MissionTaskStatus;
  summary?: string | null;
  error?: string | null;
  retry_count?: number;
  started_at?: string | null;
  completed_at?: string | null;
}
