import type {
  ValidationClientResult,
  ValidationFeedbackCreateInput,
  ValidationFeedbackNoteRecord,
  ValidationHypothesisCreateInput,
  ValidationHypothesisRecord,
  ValidationHypothesisUpdateInput,
  ValidationLeadCreateInput,
  ValidationLeadRecord,
  ValidationLeadUpdateInput,
  ValidationPersonaCreateInput,
  ValidationPersonaRecord,
  ValidationPersonaUpdateInput,
  ValidationWorkspace,
  ValidationWorkspaceSeedResult,
} from "@/types/validation-ui";

const SCHEMA_MISSING =
  "Customer validation tables are not available yet. Ask Satvik to confirm supabase/validation.sql was applied in Supabase.";
const BACKEND_MISSING = "Customer validation backend is not available yet.";
const UNAUTHENTICATED = "Sign in to use Customer Validation.";

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
  return `/api/businesses/${encodeURIComponent(businessId)}/validation${suffix}`;
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
  if (code === "validation_schema_missing") return SCHEMA_MISSING;
  if (code === "backend_missing" || status === 404 || status === 405) return BACKEND_MISSING;
  if (code === "unauthenticated" || status === 401) return UNAUTHENTICATED;

  if (isRecord(payload) && typeof payload.error === "string" && payload.error.trim()) {
    return payload.error;
  }

  return fallback;
}

async function requestValidation<T>(
  path: string,
  init: RequestInit | undefined,
  fallbackError: string
): Promise<ValidationClientResult<T>> {
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
      error: "Could not reach the customer validation backend.",
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

export function fetchValidationWorkspace(
  businessId: string
): Promise<ValidationClientResult<ValidationWorkspace>> {
  return requestValidation<ValidationWorkspace>(
    apiPath(businessId),
    undefined,
    "Could not load customer validation workspace."
  );
}

export function seedValidationWorkspace(
  businessId: string
): Promise<ValidationClientResult<ValidationWorkspaceSeedResult>> {
  return requestValidation<ValidationWorkspaceSeedResult>(
    apiPath(businessId),
    jsonInit("POST", { action: "seed" }),
    "Could not create validation workspace."
  );
}

export function createValidationPersona(
  businessId: string,
  input: ValidationPersonaCreateInput
): Promise<ValidationClientResult<ValidationPersonaRecord>> {
  return requestValidation<ValidationPersonaRecord>(
    apiPath(businessId, "/personas"),
    jsonInit("POST", input),
    "Could not create validation persona."
  );
}

export function updateValidationPersona(
  businessId: string,
  input: ValidationPersonaUpdateInput
): Promise<ValidationClientResult<ValidationPersonaRecord>> {
  return requestValidation<ValidationPersonaRecord>(
    apiPath(businessId, "/personas"),
    jsonInit("PATCH", input),
    "Could not update validation persona."
  );
}

export function createValidationHypothesis(
  businessId: string,
  input: ValidationHypothesisCreateInput
): Promise<ValidationClientResult<ValidationHypothesisRecord>> {
  return requestValidation<ValidationHypothesisRecord>(
    apiPath(businessId, "/hypotheses"),
    jsonInit("POST", input),
    "Could not create validation hypothesis."
  );
}

export function updateValidationHypothesis(
  businessId: string,
  input: ValidationHypothesisUpdateInput
): Promise<ValidationClientResult<ValidationHypothesisRecord>> {
  return requestValidation<ValidationHypothesisRecord>(
    apiPath(businessId, "/hypotheses"),
    jsonInit("PATCH", input),
    "Could not update validation hypothesis."
  );
}

export function createValidationLead(
  businessId: string,
  input: ValidationLeadCreateInput
): Promise<ValidationClientResult<ValidationLeadRecord>> {
  return requestValidation<ValidationLeadRecord>(
    apiPath(businessId, "/leads"),
    jsonInit("POST", input),
    "Could not create validation lead."
  );
}

export function updateValidationLead(
  businessId: string,
  input: ValidationLeadUpdateInput
): Promise<ValidationClientResult<ValidationLeadRecord>> {
  return requestValidation<ValidationLeadRecord>(
    apiPath(businessId, "/leads"),
    jsonInit("PATCH", input),
    "Could not update validation lead."
  );
}

export function createValidationFeedbackNote(
  businessId: string,
  input: ValidationFeedbackCreateInput
): Promise<ValidationClientResult<ValidationFeedbackNoteRecord>> {
  return requestValidation<ValidationFeedbackNoteRecord>(
    apiPath(businessId, "/feedback"),
    jsonInit("POST", input),
    "Could not create validation feedback."
  );
}
