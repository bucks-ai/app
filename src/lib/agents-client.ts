import type { AgentRegistryView } from "@/types/agents";
import type { AgentRunListResponse } from "@/types/agent-runs";

const AGENT_RUNS_SCHEMA_MISSING =
  "Agent run history is not installed yet. Apply supabase/agent-runs.sql in Supabase.";
const BACKEND_MISSING = "Operating team backend is not available yet.";
const UNAUTHENTICATED = "Sign in to view the operating team.";

export type AgentRunListData = AgentRunListResponse & {
  _warning?: string;
};

export type InferAgentRunsResult = {
  created: number;
  skipped: number;
};

export type AgentsClientResult<T> =
  | {
      ok: true;
      data: T;
      warning?: string;
    }
  | {
      ok: false;
      code: string;
      error: string;
    };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function resolveCode(status: number, payload: unknown, fallback: string) {
  if (isRecord(payload) && typeof payload.code === "string" && payload.code.trim()) {
    return payload.code;
  }

  if (status === 404 || status === 405) return "backend_missing";
  if (status === 401) return "unauthenticated";
  return fallback;
}

function friendlyError(status: number, code: string, payload: unknown, fallback: string) {
  if (code === "agent_runs_schema_missing") return AGENT_RUNS_SCHEMA_MISSING;
  if (code === "backend_missing" || status === 404 || status === 405) return BACKEND_MISSING;
  if (code === "unauthenticated" || status === 401) return UNAUTHENTICATED;

  if (isRecord(payload) && typeof payload.error === "string" && payload.error.trim()) {
    return payload.error;
  }

  return fallback;
}

async function requestAgents<T>(
  path: string,
  init: RequestInit | undefined,
  fallbackError: string
): Promise<AgentsClientResult<T>> {
  try {
    const response = await fetch(path, init);
    const payload = await readJson(response);
    const code = resolveCode(response.status, payload, "request_failed");

    if (!response.ok || (isRecord(payload) && payload.ok === false)) {
      return {
        ok: false,
        code,
        error: friendlyError(response.status, code, payload, fallbackError),
      };
    }

    const data = isRecord(payload) && "data" in payload ? payload.data : payload;
    return { ok: true, data: data as T };
  } catch {
    return {
      ok: false,
      code: "network_error",
      error: "Could not reach the operating team backend.",
    };
  }
}

function apiPath(businessId: string, suffix = "") {
  return `/api/businesses/${encodeURIComponent(businessId)}${suffix}`;
}

export function fetchAgentRegistry(
  businessId: string
): Promise<AgentsClientResult<AgentRegistryView>> {
  return requestAgents<AgentRegistryView>(
    apiPath(businessId, "/agents"),
    undefined,
    "Could not load the operating team."
  );
}

export async function fetchAgentRuns(
  businessId: string
): Promise<AgentsClientResult<AgentRunListData>> {
  const result = await requestAgents<AgentRunListData>(
    apiPath(businessId, "/agent-runs"),
    undefined,
    "Could not load agent run history."
  );

  if (result.ok && result.data._warning) {
    return {
      ...result,
      warning: AGENT_RUNS_SCHEMA_MISSING,
    };
  }

  return result;
}

export function inferAgentRuns(
  businessId: string
): Promise<AgentsClientResult<InferAgentRunsResult>> {
  return requestAgents<InferAgentRunsResult>(
    apiPath(businessId, "/agent-runs/infer"),
    { method: "POST" },
    "Could not build agent run history."
  );
}
