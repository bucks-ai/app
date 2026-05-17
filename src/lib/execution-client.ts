import type {
  BusinessExecutionStatus,
  ExecutionAsset,
  ExecutionBlocker,
  ExecutionHealth,
  ExecutionMilestone,
  ExecutionMilestoneStatus,
  ExecutionNextAction,
  ExecutionPhase,
  ExecutionStatusResponse,
  ExecutionTimelineEvent,
  ExecutionTimelineResponse,
} from "@/types/execution-ui";

const EXECUTION_API_UNAVAILABLE =
  "Execution status backend is not available yet. Merge backend branch first.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
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

function unwrapData(payload: unknown) {
  return isRecord(payload) && "data" in payload ? payload.data : payload;
}

function normalizeErrorCode(status: number, payload: unknown) {
  if (isRecord(payload) && typeof payload.code === "string" && payload.code.trim()) {
    return payload.code;
  }

  if (status === 404 || status === 405) return "api_unavailable";
  if (status === 401 || status === 403) return "unauthorized";
  return "request_failed";
}

function friendlyError(status: number, code: string, payload: unknown) {
  const rawError =
    isRecord(payload) && typeof payload.error === "string" && payload.error.trim()
      ? payload.error
      : null;

  if (code === "api_unavailable" || status === 404 || status === 405) {
    return EXECUTION_API_UNAVAILABLE;
  }

  if (code === "unauthorized" || status === 401 || status === 403) {
    return "Sign in to view execution status for this business.";
  }

  return rawError ?? "Execution status could not be loaded.";
}

function normalizePhase(value: unknown): ExecutionPhase {
  switch (value) {
    case "idea_captured":
    case "blueprint":
    case "permissions":
    case "github":
    case "scaffold":
    case "vercel":
    case "deployment":
    case "validation":
    case "blocked":
    case "completed":
      return value;
    default:
      return "idea_captured";
  }
}

function normalizeHealth(value: unknown): ExecutionHealth {
  switch (value) {
    case "on_track":
    case "needs_attention":
    case "blocked":
    case "complete":
      return value;
    default:
      return "needs_attention";
  }
}

function normalizeMilestoneStatus(value: unknown): ExecutionMilestoneStatus {
  switch (value) {
    case "pending":
    case "in_progress":
    case "complete":
    case "blocked":
    case "skipped":
      return value;
    default:
      return "pending";
  }
}

function normalizeMilestone(value: unknown): ExecutionMilestone | null {
  const record = asRecord(value);
  if (!record) return null;

  const id = normalizePhase(record.id ?? record.phase);
  const label = asString(record.label) ?? asString(record.title);

  if (!label) return null;

  return {
    id,
    label,
    status: normalizeMilestoneStatus(record.status),
    description: asString(record.description),
    completedAt: asString(record.completedAt) ?? asString(record.completed_at),
    href: asString(record.href),
  };
}

function normalizeTimelineEvent(value: unknown): ExecutionTimelineEvent | null {
  const record = asRecord(value);
  if (!record) return null;

  const id = asString(record.id);
  const title = asString(record.title) ?? asString(record.event) ?? asString(record.message);
  const createdAt = asString(record.createdAt) ?? asString(record.created_at);

  if (!id || !title || !createdAt) return null;

  return {
    id,
    category: asString(record.category) ?? asString(record.activityType) ?? "execution",
    title,
    message: asString(record.message),
    actor: asString(record.actor),
    status: asString(record.status),
    createdAt,
    metadata: asRecord(record.metadata),
  };
}

function normalizeBlocker(value: unknown): ExecutionBlocker | null {
  const record = asRecord(value);
  if (!record) return null;

  const id = asString(record.id);
  const title = asString(record.title);
  if (!id || !title) return null;

  const severity = record.severity === "critical" || record.severity === "blocked"
    ? record.severity
    : "warning";

  return {
    id,
    title,
    description: asString(record.description),
    severity,
    owner: record.owner === "bucks_ai" ? "bucks_ai" : "founder",
    href: asString(record.href),
  };
}

function normalizeNextAction(value: unknown): ExecutionNextAction | null {
  const record = asRecord(value);
  if (!record) return null;

  const id = asString(record.id);
  const title = asString(record.title);
  if (!id || !title) return null;

  return {
    id,
    title,
    description: asString(record.description),
    actor: record.actor === "bucks_ai" ? "bucks_ai" : "founder",
    href: asString(record.href),
    priority:
      record.priority === "high" || record.priority === "low" ? record.priority : "medium",
  };
}

function normalizeAsset(value: unknown): ExecutionAsset | null {
  const record = asRecord(value);
  if (!record) return null;

  const id = asString(record.id);
  const label = asString(record.label) ?? asString(record.title);
  if (!id || !label) return null;

  const type =
    record.type === "github_repo" ||
    record.type === "vercel_project" ||
    record.type === "deployment_url" ||
    record.type === "blueprint" ||
    record.type === "tool_permissions"
      ? record.type
      : "other";

  return {
    id,
    label,
    type,
    url: asString(record.url),
    status: asString(record.status),
    description: asString(record.description),
  };
}

function normalizeExecutionStatus(value: unknown): BusinessExecutionStatus | null {
  const record = asRecord(value);
  if (!record) return null;

  const businessId = asString(record.businessId) ?? asString(record.business_id);
  if (!businessId) return null;

  const rawNextActions = record.nextActions ?? record.next_actions;
  const progressPercent = Math.max(
    0,
    Math.min(100, Math.round(asNumber(record.progressPercent ?? record.progress_percent) ?? 0))
  );

  return {
    businessId,
    currentPhase: normalizePhase(record.currentPhase ?? record.current_phase),
    health: normalizeHealth(record.health),
    progressPercent,
    milestones: Array.isArray(record.milestones)
      ? record.milestones
          .map(normalizeMilestone)
          .filter((item): item is ExecutionMilestone => Boolean(item))
      : [],
    blockers: Array.isArray(record.blockers)
      ? record.blockers
          .map(normalizeBlocker)
          .filter((item): item is ExecutionBlocker => Boolean(item))
      : [],
    nextActions: Array.isArray(rawNextActions)
      ? rawNextActions
          .map(normalizeNextAction)
          .filter((item): item is ExecutionNextAction => Boolean(item))
      : [],
    assets: Array.isArray(record.assets)
      ? record.assets
          .map(normalizeAsset)
          .filter((item): item is ExecutionAsset => Boolean(item))
      : [],
    timeline: Array.isArray(record.timeline)
      ? record.timeline
          .map(normalizeTimelineEvent)
          .filter((item): item is ExecutionTimelineEvent => Boolean(item))
      : [],
    updatedAt: asString(record.updatedAt) ?? asString(record.updated_at),
  };
}

export async function fetchBusinessExecutionStatus(
  businessId: string
): Promise<ExecutionStatusResponse> {
  try {
    const response = await fetch(
      `/api/businesses/${encodeURIComponent(businessId)}/execution-status`
    );
    const payload = await readJson(response);
    const code = normalizeErrorCode(response.status, payload);

    if (!response.ok || (isRecord(payload) && payload.ok === false)) {
      return { ok: false, code, error: friendlyError(response.status, code, payload) };
    }

    const data = normalizeExecutionStatus(unwrapData(payload));
    if (!data) {
      return {
        ok: false,
        code: "invalid_response",
        error: "Execution status backend returned data in an unexpected shape.",
      };
    }

    return {
      ok: true,
      data,
      warning: isRecord(payload) ? asString(payload.warning) ?? undefined : undefined,
    };
  } catch {
    return {
      ok: false,
      code: "network_error",
      error: "Could not reach the execution status route.",
    };
  }
}

export async function fetchExecutionTimeline(
  businessId: string
): Promise<ExecutionTimelineResponse> {
  try {
    const response = await fetch(
      `/api/businesses/${encodeURIComponent(businessId)}/execution-timeline`
    );
    const payload = await readJson(response);
    const code = normalizeErrorCode(response.status, payload);

    if (!response.ok || (isRecord(payload) && payload.ok === false)) {
      return { ok: false, code, error: friendlyError(response.status, code, payload) };
    }

    const source = unwrapData(payload);
    const rawEvents = Array.isArray(source)
      ? source
      : isRecord(source) && Array.isArray(source.timeline)
        ? source.timeline
        : [];

    return {
      ok: true,
      data: rawEvents
        .map(normalizeTimelineEvent)
        .filter((item): item is ExecutionTimelineEvent => Boolean(item)),
      warning: isRecord(payload) ? asString(payload.warning) ?? undefined : undefined,
    };
  } catch {
    return {
      ok: false,
      code: "network_error",
      error: "Could not reach the execution timeline route.",
    };
  }
}
