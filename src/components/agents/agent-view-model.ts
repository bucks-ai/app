import type {
  AgentRegistrySummary,
  AgentTemplateId,
} from "@/types/agents";
import type { AgentRunRecord, AgentRunSummary } from "@/types/agent-runs";

export type OperatingTeamActionTone = "warning" | "danger" | "accent" | "neutral";

export type OperatingTeamAction = {
  title: string;
  description: string;
  tone: OperatingTeamActionTone;
};

export function humanizeAgentValue(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatAgentTime(value?: string | null): string {
  if (!value) return "No timestamp";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No timestamp";

  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function getAgentRunTimestamp(run: AgentRunRecord): number {
  const value = run.completed_at ?? run.started_at ?? run.updated_at ?? run.created_at;
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

export function formatAgentRunWindow(run: AgentRunRecord): string {
  const started = formatAgentTime(run.started_at ?? run.created_at);
  const completed = run.completed_at ? formatAgentTime(run.completed_at) : null;

  if (completed) return `Started ${started} / Completed ${completed}`;
  return `Started ${started} / Not completed`;
}

export function latestRunByAgent(
  runs: AgentRunRecord[]
): Partial<Record<AgentTemplateId, AgentRunRecord>> {
  const latest: Partial<Record<AgentTemplateId, AgentRunRecord>> = {};

  for (const run of runs) {
    const current = latest[run.agent_id];
    if (!current || getAgentRunTimestamp(run) > getAgentRunTimestamp(current)) {
      latest[run.agent_id] = run;
    }
  }

  return latest;
}

export function resolveOperatingTeamNextAction(
  registrySummary: AgentRegistrySummary,
  runSummary: AgentRunSummary | null,
  agentRunsSchemaMissing: boolean
): OperatingTeamAction {
  const blockedOrWaiting = registrySummary.blockedCount + registrySummary.waitingCount;

  if (agentRunsSchemaMissing) {
    return {
      title: "Apply Agent Runs SQL",
      description: "Run history is waiting on supabase/agent-runs.sql before inference can persist.",
      tone: "warning",
    };
  }

  if (blockedOrWaiting > 0) {
    return {
      title: "Review blocked agents",
      description: `${blockedOrWaiting} agent${blockedOrWaiting === 1 ? "" : "s"} need a dependency or approval before they can move.`,
      tone: "danger",
    };
  }

  if ((runSummary?.totalRuns ?? 0) === 0) {
    return {
      title: "Build agent run history",
      description: "Backfill inferred runs from existing activity logs to make the team timeline useful.",
      tone: "accent",
    };
  }

  if (registrySummary.activeCount > 0) {
    return {
      title: "Monitor active agents",
      description: "At least one agent is currently executing.",
      tone: "accent",
    };
  }

  return {
    title: "Open Operating Team",
    description: "Review node coverage, latest run history, and the next system handoff.",
    tone: "neutral",
  };
}
