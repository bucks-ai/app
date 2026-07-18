// TypeScript types for all Supabase database tables.
// These mirror the schema in supabase/schema.sql.

// ---------------------------------------------------------------------------
// Row types — shape of a row returned by SELECT
// ---------------------------------------------------------------------------

export interface ProfileRecord {
  id: string;
  email: string | null;
  created_at: string;
  updated_at: string;
}

export interface BusinessRecord {
  id: string;
  user_id: string;
  idea_name: string;
  one_line_idea: string | null;
  idea_description: string | null;
  target_customer: string | null;
  business_type: string | null;
  primary_goal: string | null;
  success_metric: string | null;
  budget: string | null;
  timeline: string | null;
  autonomy_preference: string | null;
  spending_limit: string | null;
  hard_constraints: string | null;
  human_only_actions: string | null;
  forbidden_actions: string | null;
  preferred_tools: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface BusinessBlueprintRecord {
  id: string;
  business_id: string;
  user_id: string;
  blueprint: Record<string, unknown>;
  created_at: string;
}

export interface HumanRequiredActionRecord {
  id: string;
  business_id: string;
  user_id: string;
  title: string;
  description: string | null;
  status: string;
  risk_level: string;
  created_at: string;
  updated_at: string;
}

export interface AgentActivityLogRecord {
  id: string;
  business_id: string;
  user_id: string;
  activity_type: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ToolPermissionRecord {
  id: string;
  user_id: string;
  business_id: string | null;
  tool_id: string;
  tool_name: string;
  status: string;
  setup_status: string;
  risk_level: string;
  permissions: string[];
  created_at: string;
  updated_at: string;
}

// Agent Runs v1 — mirrors public.agent_runs in supabase/agent-runs.sql
export interface AgentRunDatabaseRecord {
  id: string;
  business_id: string;
  user_id: string;
  agent_id: string;
  node_id: string;
  title: string;
  summary: string | null;
  status: string;
  source: string;
  trigger: string | null;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  artifacts: Record<string, unknown>[];
  error: Record<string, unknown> | null;
  related_activity_log_ids: string[];
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

// M4a — mirrors public.approvals in supabase/m4a-approvals-queue.sql.
// Not business-scoped: these mirror the runner's file-based outbox/inbox
// approval gates (merge/SQL/resource/strategic review), owned by the
// operator account, not any one founder's business.
export interface ApprovalRecord {
  id: string;
  user_id: string;
  request_type: string;
  request_id: string;
  source_file: string;
  title: string;
  body: string;
  status: string;
  decided_by: string | null;
  decided_at: string | null;
  inbox_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

// Mirrors public.missions in supabase/missions.sql, plus the runner_target
// column from supabase/migrations/0003_missions_runner_target.sql.
//
// CRITICAL SAFETY: runner_target gates what the runner is allowed to claim
// (runner/langgraph/tools/seeded_mission_queue.py::fetch_next_queued_mission).
// "self" = runner may execute against the bucks-ai repo. "business" = created
// via the app's Execute button for a customer business; must sit queued and
// never be claimed until M4b lands per-business sandboxing.
export interface MissionRecord {
  id: string;
  business_id: string;
  user_id: string;
  name: string;
  goal: string | null;
  status: string;
  runner_target: "self" | "business";
  source_file: string | null;
  task_count: number;
  completed_task_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

// Mirrors public.mission_tasks in supabase/missions.sql.
export interface MissionTaskRecord {
  id: string;
  mission_id: string;
  business_id: string;
  user_id: string;
  task_id: string;
  title: string;
  description: string | null;
  type: string;
  branch: string;
  preferred_worker: string | null;
  position: number;
  status: string;
  summary: string | null;
  error: string | null;
  retry_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

// Mirrors public.business_sandbox in supabase/migrations/0004_business_sandbox.sql.
//
// CRITICAL SAFETY: github_token_secret_name / vercel_token_secret_name are
// NAMES of entries in the runner's own env/secret store — never the token
// values themselves. See supabase/migrations/README.md for the convention.
export type SandboxStatus = "unconfigured" | "partial" | "configured";

export interface BusinessSandboxRecord {
  id: string;
  business_id: string;
  user_id: string;
  repo_full_name: string | null;
  vercel_project_id: string | null;
  github_token_secret_name: string | null;
  vercel_token_secret_name: string | null;
  status: SandboxStatus;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Insert types — fields required when creating a new row.
// Defined as flat interfaces (not intersections) so Supabase's generic
// type machinery can index into them without resolving to never.
// ---------------------------------------------------------------------------

export interface NewBusinessInput {
  user_id: string;
  idea_name: string;
  one_line_idea?: string | null;
  idea_description?: string | null;
  target_customer?: string | null;
  business_type?: string | null;
  primary_goal?: string | null;
  success_metric?: string | null;
  budget?: string | null;
  timeline?: string | null;
  autonomy_preference?: string | null;
  spending_limit?: string | null;
  hard_constraints?: string | null;
  human_only_actions?: string | null;
  forbidden_actions?: string | null;
  preferred_tools?: string | null;
  status?: string;
}

export interface NewBusinessBlueprintInput {
  business_id: string;
  user_id: string;
  blueprint: Record<string, unknown>;
}

export interface NewHumanRequiredActionInput {
  business_id: string;
  user_id: string;
  title: string;
  description?: string | null;
  status?: string;
  risk_level?: string;
}

export interface NewAgentActivityLogInput {
  business_id: string;
  user_id: string;
  activity_type: string;
  message: string;
  metadata?: Record<string, unknown>;
}

export interface NewToolPermissionInput {
  user_id: string;
  tool_id: string;
  tool_name: string;
  business_id?: string | null;
  status?: string;
  setup_status?: string;
  risk_level?: string;
  permissions?: string[];
}

export interface NewAgentRunInput {
  business_id: string;
  user_id: string;
  agent_id: string;
  node_id: string;
  title: string;
  summary?: string | null;
  status?: string;
  source?: string;
  trigger?: string | null;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  artifacts?: Record<string, unknown>[];
  error?: Record<string, unknown> | null;
  related_activity_log_ids?: string[];
  started_at?: string | null;
  completed_at?: string | null;
}

export interface NewMissionInput {
  business_id: string;
  user_id: string;
  name: string;
  goal?: string | null;
  status?: string;
  runner_target?: "self" | "business";
  source_file?: string | null;
  task_count?: number;
}

export interface NewMissionTaskInput {
  mission_id: string;
  business_id: string;
  user_id: string;
  task_id: string;
  title: string;
  description?: string | null;
  type?: string;
  branch: string;
  preferred_worker?: string | null;
  position: number;
  status?: string;
}

export interface NewBusinessSandboxInput {
  business_id: string;
  user_id: string;
  repo_full_name?: string | null;
  vercel_project_id?: string | null;
  github_token_secret_name?: string | null;
  vercel_token_secret_name?: string | null;
  status?: SandboxStatus;
}

// ---------------------------------------------------------------------------
// Supabase Database generic type (used by createClient<Database>)
// ---------------------------------------------------------------------------

export type Database = {
  public: {
    Tables: {
      profiles: {
        Row: ProfileRecord;
        Insert: Partial<ProfileRecord> & Pick<ProfileRecord, "id">;
        Update: Partial<ProfileRecord>;
      };
      businesses: {
        Row: BusinessRecord;
        Insert: NewBusinessInput;
        Update: Partial<BusinessRecord>;
      };
      business_blueprints: {
        Row: BusinessBlueprintRecord;
        Insert: NewBusinessBlueprintInput;
        Update: Partial<BusinessBlueprintRecord>;
      };
      human_required_actions: {
        Row: HumanRequiredActionRecord;
        Insert: NewHumanRequiredActionInput;
        Update: Partial<HumanRequiredActionRecord>;
      };
      agent_activity_logs: {
        Row: AgentActivityLogRecord;
        Insert: NewAgentActivityLogInput;
        Update: Partial<AgentActivityLogRecord>;
      };
      tool_permissions: {
        Row: ToolPermissionRecord;
        Insert: NewToolPermissionInput;
        Update: Partial<ToolPermissionRecord>;
      };
      agent_runs: {
        Row: AgentRunDatabaseRecord;
        Insert: NewAgentRunInput;
        Update: Partial<AgentRunDatabaseRecord>;
      };
      missions: {
        Row: MissionRecord;
        Insert: NewMissionInput;
        Update: Partial<MissionRecord>;
      };
      mission_tasks: {
        Row: MissionTaskRecord;
        Insert: NewMissionTaskInput;
        Update: Partial<MissionTaskRecord>;
      };
      business_sandbox: {
        Row: BusinessSandboxRecord;
        Insert: NewBusinessSandboxInput;
        Update: Partial<BusinessSandboxRecord>;
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
  };
};
