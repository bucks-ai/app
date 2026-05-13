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
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
  };
};
