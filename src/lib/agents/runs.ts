// Agent Runs v1 — helper functions.
// Reads and writes the agent_runs table. Requires the authenticated user's session.
//
// If the agent_runs table does not exist (SQL not yet applied), functions return
// { data: null, error: "...", code: "agent_runs_schema_missing" } rather than crashing.
//
// Activity-to-agent mapping:
//   blueprint_generated / business_blueprint_saved → blueprint
//   github_repo_created                            → repository
//   github_next_scaffold_prepared / scaffold_prepared → scaffold
//   vercel_project_created                         → deployment_status
//   deployment_status_refreshed / deployment_ready / deployment_failed → deployment_status
//   validation_workspace_seeded                    → persona, hypothesis
//   validation_feedback_added                      → feedback_analysis
//   research_workspace_generated                   → market_research, customer_segment,
//                                                     competitor, monetization,
//                                                     distribution, risk
//   research_report_created                        → opportunity_scoring
//   tool_permission_approved / tool_permissions_seeded → tool_permission
//   next_action_resolved                           → next_action

import { createSupabaseServerClient } from "@/lib/supabase/server";
import {
  AGENT_REGISTRY,
  getAgentTemplate,
} from "@/lib/agents/registry";
import type { AgentTemplateId, AgentNodeId } from "@/types/agents";
import type { AgentActivityLogRecord } from "@/types/database";
import type {
  AgentRunRecord,
  AgentRunSummary,
  AgentRunCreateInput,
  AgentRunUpdateInput,
  AgentRunTimelineItem,
  AgentRunArtifact,
  AgentRunStatus,
  AgentRunSource,
  AgentRunTrigger,
} from "@/types/agent-runs";

// ---------------------------------------------------------------------------
// Result wrapper
// ---------------------------------------------------------------------------

type Result<T> =
  | { data: T; error: null; code?: undefined }
  | { data: null; error: string; code: string };

function ok<T>(data: T): Result<T> {
  return { data, error: null };
}

function err<T>(message: string, code = "unknown_error"): Result<T> {
  return { data: null, error: message, code };
}

// ---------------------------------------------------------------------------
// Schema guard — detect missing table gracefully
// ---------------------------------------------------------------------------

function isSchemaMissing(error: { code?: string; message?: string } | null): boolean {
  if (!error) return false;
  const msg = error.message ?? "";
  return (
    error.code === "42P01" ||
    msg.includes("does not exist") ||
    msg.includes("relation") ||
    msg.includes("agent_runs")
  );
}

// ---------------------------------------------------------------------------
// Agent ID validation
// ---------------------------------------------------------------------------

function isKnownAgentId(agentId: string): agentId is AgentTemplateId {
  return agentId in AGENT_REGISTRY;
}

// ---------------------------------------------------------------------------
// Activity type → agent id mapping
// ---------------------------------------------------------------------------

type ActivityMapping = {
  agentId: AgentTemplateId;
  trigger: AgentRunTrigger;
  titleFn: (log: AgentActivityLogRecord) => string;
  artifacts?: (log: AgentActivityLogRecord) => AgentRunArtifact[];
};

function buildArtifactsFromMetadata(
  log: AgentActivityLogRecord,
  type: string,
  label: string,
  urlKey?: string
): AgentRunArtifact[] {
  const meta = log.metadata ?? {};
  const url = urlKey ? (meta[urlKey] as string | undefined) : undefined;
  return [{ type, label, url, metadata: meta }];
}

const ACTIVITY_MAPPINGS: Record<string, ActivityMapping[]> = {
  blueprint_created: [
    {
      agentId: "blueprint",
      trigger: "blueprint_generated",
      titleFn: () => "Blueprint generated",
      artifacts: (log) =>
        buildArtifactsFromMetadata(log, "blueprint", "Launch blueprint"),
    },
  ],
  business_blueprint_saved: [
    {
      agentId: "blueprint",
      trigger: "blueprint_generated",
      titleFn: () => "Blueprint saved",
    },
  ],
  github_repo_created: [
    {
      agentId: "repository",
      trigger: "repo_created",
      titleFn: (log) => {
        const name = (log.metadata?.repo_name as string) ?? "GitHub repository";
        return `Repository created: ${name}`;
      },
      artifacts: (log) =>
        buildArtifactsFromMetadata(log, "github_repo", "GitHub repository", "repo_url"),
    },
  ],
  github_next_scaffold_prepared: [
    {
      agentId: "scaffold",
      trigger: "scaffold_prepared",
      titleFn: () => "Next.js scaffold prepared",
      artifacts: (log) =>
        buildArtifactsFromMetadata(log, "github_repo", "Scaffold commit", "repo_url"),
    },
  ],
  scaffold_prepared: [
    {
      agentId: "scaffold",
      trigger: "scaffold_prepared",
      titleFn: () => "Scaffold prepared",
    },
  ],
  vercel_project_created: [
    {
      agentId: "deployment_status",
      trigger: "vercel_project_created",
      titleFn: (log) => {
        const name = (log.metadata?.project_name as string) ?? "Vercel project";
        return `Vercel project created: ${name}`;
      },
      artifacts: (log) =>
        buildArtifactsFromMetadata(log, "vercel_project", "Vercel project", "project_url"),
    },
  ],
  deployment_status_refreshed: [
    {
      agentId: "deployment_status",
      trigger: "deployment_status_refreshed",
      titleFn: () => "Deployment status refreshed",
    },
  ],
  deployment_ready: [
    {
      agentId: "deployment_status",
      trigger: "deployment_status_refreshed",
      titleFn: (log) => {
        const url = (log.metadata?.deployment_url as string) ?? "deployment";
        return `Deployment ready: ${url}`;
      },
      artifacts: (log) =>
        buildArtifactsFromMetadata(log, "deployment", "Live deployment", "deployment_url"),
    },
  ],
  deployment_failed: [
    {
      agentId: "deployment_status",
      trigger: "deployment_status_refreshed",
      titleFn: () => "Deployment failed",
    },
  ],
  validation_workspace_seeded: [
    {
      agentId: "persona",
      trigger: "validation_workspace_seeded",
      titleFn: () => "Personas seeded from blueprint",
    },
    {
      agentId: "hypothesis",
      trigger: "validation_workspace_seeded",
      titleFn: () => "Hypotheses seeded from blueprint",
    },
  ],
  validation_feedback_added: [
    {
      agentId: "feedback_analysis",
      trigger: "manual",
      titleFn: () => "Customer feedback recorded",
    },
  ],
  research_workspace_generated: [
    {
      agentId: "market_research",
      trigger: "research_workspace_generated",
      titleFn: () => "Market research workspace generated",
    },
    {
      agentId: "customer_segment",
      trigger: "research_workspace_generated",
      titleFn: () => "Customer segments seeded",
    },
    {
      agentId: "competitor",
      trigger: "research_workspace_generated",
      titleFn: () => "Competitor landscape mapped",
    },
    {
      agentId: "monetization",
      trigger: "research_workspace_generated",
      titleFn: () => "Monetisation models seeded",
    },
    {
      agentId: "distribution",
      trigger: "research_workspace_generated",
      titleFn: () => "Distribution channels mapped",
    },
    {
      agentId: "risk",
      trigger: "research_workspace_generated",
      titleFn: () => "Business risks identified",
    },
  ],
  research_report_created: [
    {
      agentId: "opportunity_scoring",
      trigger: "research_workspace_generated",
      titleFn: () => "Opportunity score computed",
    },
  ],
  tool_permissions_seeded: [
    {
      agentId: "tool_permission",
      trigger: "tool_permission_approved",
      titleFn: () => "Tool permission queue seeded",
    },
  ],
  tool_permission_approved: [
    {
      agentId: "tool_permission",
      trigger: "tool_permission_approved",
      titleFn: (log) => {
        const tool = (log.metadata?.tool_name as string) ?? "tool";
        return `Tool approved: ${tool}`;
      },
    },
  ],
  next_action_resolved: [
    {
      agentId: "next_action",
      trigger: "next_action_resolved",
      titleFn: () => "Next action resolved",
    },
  ],
};

// ---------------------------------------------------------------------------
// Convert a single activity log to zero or more AgentRunCreateInput objects
// ---------------------------------------------------------------------------

function activityLogToRunInputs(
  log: AgentActivityLogRecord
): AgentRunCreateInput[] {
  const mappings = ACTIVITY_MAPPINGS[log.activity_type];
  if (!mappings || mappings.length === 0) return [];

  return mappings.map((m) => {
    const template = getAgentTemplate(m.agentId);
    const nodeId: AgentNodeId = template?.node ?? "orchestration";

    return {
      business_id: log.business_id,
      user_id: log.user_id,
      agent_id: m.agentId,
      node_id: nodeId,
      title: m.titleFn(log),
      status: "completed" as AgentRunStatus,
      source: "activity_log_backfill" as AgentRunSource,
      trigger: m.trigger,
      input: {},
      output: log.metadata ?? {},
      artifacts: m.artifacts ? m.artifacts(log) : [],
      related_activity_log_ids: [log.id],
      started_at: log.created_at,
      completed_at: log.created_at,
    };
  });
}

// ---------------------------------------------------------------------------
// Read helpers
// ---------------------------------------------------------------------------

export async function getAgentRunsForBusiness(
  businessId: string
): Promise<Result<AgentRunRecord[]>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) {
    return err("Supabase is not configured.", "supabase_not_configured");
  }

  const { data, error } = await supabase
    .from("agent_runs")
    .select("*")
    .eq("business_id", businessId)
    .order("updated_at", { ascending: false, nullsFirst: false })
    .order("completed_at", { ascending: false, nullsFirst: false })
    .order("started_at", { ascending: false, nullsFirst: false })
    .order("created_at", { ascending: false });

  if (error) {
    if (isSchemaMissing(error)) {
      return err(
        "agent_runs table does not exist. Apply supabase/agent-runs.sql first.",
        "agent_runs_schema_missing"
      );
    }
    return err(error.message, "agent_runs_fetch_failed");
  }

  return ok((data ?? []) as AgentRunRecord[]);
}

export async function getAgentRunSummaryForBusiness(
  businessId: string
): Promise<Result<AgentRunSummary>> {
  const runsResult = await getAgentRunsForBusiness(businessId);

  if (runsResult.error || !runsResult.data) {
    if (runsResult.code === "agent_runs_schema_missing") {
      return ok({
        businessId,
        totalRuns: 0,
        completedRuns: 0,
        failedRuns: 0,
        runningRuns: 0,
        blockedRuns: 0,
        waitingRuns: 0,
        lastRunAt: null,
        agentsCovered: [],
        generatedAt: new Date().toISOString(),
      });
    }
    return err(
      runsResult.error ?? "Could not load runs.",
      runsResult.code ?? "agent_runs_fetch_failed"
    );
  }

  const runs = runsResult.data;
  const agentsCovered = [
    ...new Set(runs.map((r) => r.agent_id)),
  ] as AgentTemplateId[];

  const lastRun = runs.reduce<string | null>((latest, r) => {
    const ts = r.completed_at ?? r.created_at;
    if (!latest || ts > latest) return ts;
    return latest;
  }, null);

  return ok({
    businessId,
    totalRuns: runs.length,
    completedRuns: runs.filter((r) => r.status === "completed").length,
    failedRuns: runs.filter((r) => r.status === "failed").length,
    runningRuns: runs.filter((r) => r.status === "running").length,
    blockedRuns: runs.filter((r) => r.status === "blocked").length,
    waitingRuns: runs.filter((r) => r.status === "waiting_for_approval").length,
    lastRunAt: lastRun,
    agentsCovered,
    generatedAt: new Date().toISOString(),
  });
}

export async function getLatestRunForAgent(
  businessId: string,
  agentId: string
): Promise<Result<AgentRunRecord | null>> {
  if (!isKnownAgentId(agentId)) {
    return err(`Unknown agent id: ${agentId}`, "invalid_agent_id");
  }

  const supabase = await createSupabaseServerClient();
  if (!supabase) {
    return err("Supabase is not configured.", "supabase_not_configured");
  }

  const { data, error } = await supabase
    .from("agent_runs")
    .select("*")
    .eq("business_id", businessId)
    .eq("agent_id", agentId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) {
    if (isSchemaMissing(error)) {
      return ok(null);
    }
    return err(error.message, "agent_runs_fetch_failed");
  }

  return ok((data as AgentRunRecord) ?? null);
}

// ---------------------------------------------------------------------------
// Write helpers
// ---------------------------------------------------------------------------

export async function createAgentRun(
  input: AgentRunCreateInput
): Promise<Result<AgentRunRecord>> {
  if (!isKnownAgentId(input.agent_id)) {
    return err(`Unknown agent id: ${input.agent_id}`, "invalid_agent_id");
  }

  const supabase = await createSupabaseServerClient();
  if (!supabase) {
    return err("Supabase is not configured.", "supabase_not_configured");
  }

  const { data, error } = await supabase
    .from("agent_runs")
    .insert({
      business_id: input.business_id,
      user_id: input.user_id,
      agent_id: input.agent_id,
      node_id: input.node_id,
      title: input.title,
      summary: input.summary ?? null,
      status: input.status ?? "completed",
      source: input.source,
      trigger: input.trigger ?? null,
      input: input.input ?? {},
      output: input.output ?? {},
      artifacts: input.artifacts ?? [],
      error: input.error ?? null,
      related_activity_log_ids: input.related_activity_log_ids ?? [],
      started_at: input.started_at ?? null,
      completed_at: input.completed_at ?? null,
    })
    .select()
    .single();

  if (error) {
    if (isSchemaMissing(error)) {
      return err(
        "agent_runs table does not exist. Apply supabase/agent-runs.sql first.",
        "agent_runs_schema_missing"
      );
    }
    return err(error.message, "agent_run_create_failed");
  }

  if (!data) {
    return err("Failed to create agent run.", "agent_run_create_failed");
  }

  return ok(data as AgentRunRecord);
}

export async function updateAgentRun(
  input: AgentRunUpdateInput
): Promise<Result<AgentRunRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) {
    return err("Supabase is not configured.", "supabase_not_configured");
  }

  const update: Record<string, unknown> = {};
  if (input.title !== undefined) update.title = input.title;
  if (input.summary !== undefined) update.summary = input.summary;
  if (input.status !== undefined) update.status = input.status;
  if (input.output !== undefined) update.output = input.output;
  if (input.artifacts !== undefined) update.artifacts = input.artifacts;
  if (input.error !== undefined) update.error = input.error;
  if (input.related_activity_log_ids !== undefined)
    update.related_activity_log_ids = input.related_activity_log_ids;
  if (input.started_at !== undefined) update.started_at = input.started_at;
  if (input.completed_at !== undefined) update.completed_at = input.completed_at;

  const { data, error } = await supabase
    .from("agent_runs")
    .update(update)
    .eq("id", input.id)
    .select()
    .single();

  if (error) {
    if (isSchemaMissing(error)) {
      return err(
        "agent_runs table does not exist. Apply supabase/agent-runs.sql first.",
        "agent_runs_schema_missing"
      );
    }
    return err(error.message, "agent_run_update_failed");
  }

  if (!data) {
    return err("Agent run not found.", "agent_run_update_failed");
  }

  return ok(data as AgentRunRecord);
}

// ---------------------------------------------------------------------------
// Back-fill / inference
// ---------------------------------------------------------------------------

export async function createAgentRunFromActivityLog(
  log: AgentActivityLogRecord
): Promise<Result<AgentRunRecord[]>> {
  const inputs = activityLogToRunInputs(log);
  if (inputs.length === 0) return ok([]);

  const created: AgentRunRecord[] = [];
  for (const input of inputs) {
    const result = await createAgentRun(input);
    if (result.error) {
      return err(result.error, result.code ?? "agent_run_create_failed");
    }
    created.push(result.data!);
  }

  return ok(created);
}

export async function inferAgentRunsFromActivityLogs(
  businessId: string
): Promise<Result<{ created: number; skipped: number }>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) {
    return err("Supabase is not configured.", "supabase_not_configured");
  }

  // Load activity logs for this business
  const { data: logs, error: logsError } = await supabase
    .from("agent_activity_logs")
    .select("*")
    .eq("business_id", businessId)
    .order("created_at", { ascending: true });

  if (logsError) {
    return err(logsError.message, "activity_logs_fetch_failed");
  }

  if (!logs || logs.length === 0) {
    return ok({ created: 0, skipped: 0 });
  }

  // Load existing runs so we can skip activity logs already covered
  const { data: existingRuns, error: runsError } = await supabase
    .from("agent_runs")
    .select("related_activity_log_ids")
    .eq("business_id", businessId);

  if (runsError) {
    if (isSchemaMissing(runsError)) {
      return err(
        "agent_runs table does not exist. Apply supabase/agent-runs.sql first.",
        "agent_runs_schema_missing"
      );
    }
    return err(runsError.message, "agent_runs_fetch_failed");
  }

  // Build a set of activity log IDs already covered by existing runs
  const coveredLogIds = new Set<string>();
  for (const run of existingRuns ?? []) {
    const ids = run.related_activity_log_ids as string[] | null;
    (ids ?? []).forEach((id) => coveredLogIds.add(id));
  }

  let created = 0;
  let skipped = 0;

  for (const log of logs as AgentActivityLogRecord[]) {
    // Skip if this log is already covered by an existing run
    if (coveredLogIds.has(log.id)) {
      skipped++;
      continue;
    }

    const inputs = activityLogToRunInputs(log);
    if (inputs.length === 0) {
      skipped++;
      continue;
    }

    for (const input of inputs) {
      const result = await createAgentRun(input);
      if (result.error) {
        if (result.code === "agent_runs_schema_missing") {
          return err(result.error, result.code);
        }
        // Non-fatal: skip this one and continue
        skipped++;
        continue;
      }
      created++;
      // Mark this log ID as covered so we don't create duplicates
      // within the same inference pass
      coveredLogIds.add(log.id);
    }
  }

  return ok({ created, skipped });
}

// ---------------------------------------------------------------------------
// Timeline helper (lightweight view)
// ---------------------------------------------------------------------------

export function toTimelineItems(runs: AgentRunRecord[]): AgentRunTimelineItem[] {
  return runs.map((r) => ({
    id: r.id,
    agentId: r.agent_id,
    nodeId: r.node_id,
    title: r.title,
    status: r.status,
    source: r.source,
    trigger: r.trigger,
    startedAt: r.started_at,
    completedAt: r.completed_at,
    createdAt: r.created_at,
    hasSummary: Boolean(r.summary),
    hasError: Boolean(r.error),
  }));
}
