import type {
  ResearchBuyerBudgetCreateInput,
  ResearchBuyerBudgetRecord,
  ResearchBuyerBudgetUpdateInput,
  ResearchClientResult,
  ResearchCompetitorCreateInput,
  ResearchCompetitorRecord,
  ResearchCompetitorUpdateInput,
  ResearchCustomerSegmentCreateInput,
  ResearchCustomerSegmentRecord,
  ResearchCustomerSegmentUpdateInput,
  ResearchDistributionChannelCreateInput,
  ResearchDistributionChannelRecord,
  ResearchDistributionChannelUpdateInput,
  ResearchEvidenceCreateInput,
  ResearchEvidenceRecord,
  ResearchHypothesisCreateInput,
  ResearchHypothesisRecord,
  ResearchHypothesisUpdateInput,
  ResearchMonetizationModelCreateInput,
  ResearchMonetizationModelRecord,
  ResearchMonetizationModelUpdateInput,
  ResearchRiskCreateInput,
  ResearchRiskRecord,
  ResearchRiskUpdateInput,
  ResearchWorkspace,
  ResearchWorkspaceGenerateResult,
} from "@/types/research-ui";

const SCHEMA_MISSING =
  "Research tables are not available yet. Confirm supabase/research.sql was applied in Supabase.";
const BACKEND_MISSING = "Research backend is not available yet.";
const UNAUTHENTICATED = "Sign in to use Research Mode.";

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

function apiPath(businessId: string, suffix = "") {
  return `/api/businesses/${encodeURIComponent(businessId)}/research${suffix}`;
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
  if (code === "research_schema_missing") return SCHEMA_MISSING;
  if (code === "backend_missing" || status === 404 || status === 405) return BACKEND_MISSING;
  if (code === "unauthenticated" || status === 401) return UNAUTHENTICATED;

  if (isRecord(payload) && typeof payload.error === "string" && payload.error.trim()) {
    return payload.error;
  }

  return fallback;
}

async function requestResearch<T>(
  path: string,
  init: RequestInit | undefined,
  fallbackError: string
): Promise<ResearchClientResult<T>> {
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
      error: "Could not reach the research backend.",
    };
  }
}

function jsonInit(method: "POST" | "PATCH", body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function fetchResearchWorkspace(
  businessId: string
): Promise<ResearchClientResult<ResearchWorkspace>> {
  return requestResearch<ResearchWorkspace>(
    apiPath(businessId),
    undefined,
    "Could not load research workspace."
  );
}

export function generateResearchWorkspace(
  businessId: string
): Promise<ResearchClientResult<ResearchWorkspaceGenerateResult>> {
  return requestResearch<ResearchWorkspaceGenerateResult>(
    apiPath(businessId),
    jsonInit("POST", { action: "generate" }),
    "Could not generate research workspace."
  );
}

export function createResearchCustomerSegment(
  businessId: string,
  input: ResearchCustomerSegmentCreateInput
): Promise<ResearchClientResult<ResearchCustomerSegmentRecord>> {
  return requestResearch<ResearchCustomerSegmentRecord>(
    apiPath(businessId, "/segments"),
    jsonInit("POST", input),
    "Could not create customer segment."
  );
}

export function updateResearchCustomerSegment(
  businessId: string,
  input: ResearchCustomerSegmentUpdateInput
): Promise<ResearchClientResult<ResearchCustomerSegmentRecord>> {
  return requestResearch<ResearchCustomerSegmentRecord>(
    apiPath(businessId, "/segments"),
    jsonInit("PATCH", input),
    "Could not update customer segment."
  );
}

export function createResearchBuyerBudget(
  businessId: string,
  input: ResearchBuyerBudgetCreateInput
): Promise<ResearchClientResult<ResearchBuyerBudgetRecord>> {
  return requestResearch<ResearchBuyerBudgetRecord>(
    apiPath(businessId, "/buyer-budgets"),
    jsonInit("POST", input),
    "Could not create buyer budget record."
  );
}

export function updateResearchBuyerBudget(
  businessId: string,
  input: ResearchBuyerBudgetUpdateInput
): Promise<ResearchClientResult<ResearchBuyerBudgetRecord>> {
  return requestResearch<ResearchBuyerBudgetRecord>(
    apiPath(businessId, "/buyer-budgets"),
    jsonInit("PATCH", input),
    "Could not update buyer budget record."
  );
}

export function createResearchCompetitor(
  businessId: string,
  input: ResearchCompetitorCreateInput
): Promise<ResearchClientResult<ResearchCompetitorRecord>> {
  return requestResearch<ResearchCompetitorRecord>(
    apiPath(businessId, "/competitors"),
    jsonInit("POST", input),
    "Could not create competitor."
  );
}

export function updateResearchCompetitor(
  businessId: string,
  input: ResearchCompetitorUpdateInput
): Promise<ResearchClientResult<ResearchCompetitorRecord>> {
  return requestResearch<ResearchCompetitorRecord>(
    apiPath(businessId, "/competitors"),
    jsonInit("PATCH", input),
    "Could not update competitor."
  );
}

export function createResearchMonetizationModel(
  businessId: string,
  input: ResearchMonetizationModelCreateInput
): Promise<ResearchClientResult<ResearchMonetizationModelRecord>> {
  return requestResearch<ResearchMonetizationModelRecord>(
    apiPath(businessId, "/monetization"),
    jsonInit("POST", input),
    "Could not create monetization model."
  );
}

export function updateResearchMonetizationModel(
  businessId: string,
  input: ResearchMonetizationModelUpdateInput
): Promise<ResearchClientResult<ResearchMonetizationModelRecord>> {
  return requestResearch<ResearchMonetizationModelRecord>(
    apiPath(businessId, "/monetization"),
    jsonInit("PATCH", input),
    "Could not update monetization model."
  );
}

export function createResearchDistributionChannel(
  businessId: string,
  input: ResearchDistributionChannelCreateInput
): Promise<ResearchClientResult<ResearchDistributionChannelRecord>> {
  return requestResearch<ResearchDistributionChannelRecord>(
    apiPath(businessId, "/distribution"),
    jsonInit("POST", input),
    "Could not create distribution channel."
  );
}

export function updateResearchDistributionChannel(
  businessId: string,
  input: ResearchDistributionChannelUpdateInput
): Promise<ResearchClientResult<ResearchDistributionChannelRecord>> {
  return requestResearch<ResearchDistributionChannelRecord>(
    apiPath(businessId, "/distribution"),
    jsonInit("PATCH", input),
    "Could not update distribution channel."
  );
}

export function createResearchRisk(
  businessId: string,
  input: ResearchRiskCreateInput
): Promise<ResearchClientResult<ResearchRiskRecord>> {
  return requestResearch<ResearchRiskRecord>(
    apiPath(businessId, "/risks"),
    jsonInit("POST", input),
    "Could not create research risk."
  );
}

export function updateResearchRisk(
  businessId: string,
  input: ResearchRiskUpdateInput
): Promise<ResearchClientResult<ResearchRiskRecord>> {
  return requestResearch<ResearchRiskRecord>(
    apiPath(businessId, "/risks"),
    jsonInit("PATCH", input),
    "Could not update research risk."
  );
}

export function createResearchHypothesis(
  businessId: string,
  input: ResearchHypothesisCreateInput
): Promise<ResearchClientResult<ResearchHypothesisRecord>> {
  return requestResearch<ResearchHypothesisRecord>(
    apiPath(businessId, "/hypotheses"),
    jsonInit("POST", input),
    "Could not create research hypothesis."
  );
}

export function updateResearchHypothesis(
  businessId: string,
  input: ResearchHypothesisUpdateInput
): Promise<ResearchClientResult<ResearchHypothesisRecord>> {
  return requestResearch<ResearchHypothesisRecord>(
    apiPath(businessId, "/hypotheses"),
    jsonInit("PATCH", input),
    "Could not update research hypothesis."
  );
}

export function createResearchEvidence(
  businessId: string,
  input: ResearchEvidenceCreateInput
): Promise<ResearchClientResult<ResearchEvidenceRecord>> {
  return requestResearch<ResearchEvidenceRecord>(
    apiPath(businessId, "/evidence"),
    jsonInit("POST", input),
    "Could not create research evidence."
  );
}
