import type { HumanRequiredActionRecord } from "@/types/database";
import type { HumanActionDecision } from "@/types/human-action-ui";

type ApiSuccess<T> = {
  ok: true;
  data: T;
};

type ApiFailure = {
  ok: false;
  error: string;
  code: "api_unavailable" | "invalid_response" | "request_failed" | "network_error";
  status?: number;
};

export type HumanActionClientResult<T> = ApiSuccess<T> | ApiFailure;

const API_UNAVAILABLE = "Actions API not available yet. Merge backend branch first.";

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

function getErrorMessage(payload: unknown, fallback: string) {
  if (!isRecord(payload)) return fallback;
  const error = payload.error ?? payload.message;
  return typeof error === "string" && error.trim() ? error : fallback;
}

export async function updateHumanAction(
  id: string,
  action: HumanActionDecision
): Promise<HumanActionClientResult<{ data: HumanRequiredActionRecord }>> {
  try {
    const response = await fetch(`/api/human-actions/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });

    const payload = await readJson(response);

    if (response.status === 404 || response.status === 405) {
      return {
        ok: false,
        error: API_UNAVAILABLE,
        code: "api_unavailable",
        status: response.status,
      };
    }

    if (!response.ok) {
      return {
        ok: false,
        error: getErrorMessage(payload, "Could not record that decision."),
        code: "request_failed",
        status: response.status,
      };
    }

    if (!isRecord(payload)) {
      return {
        ok: false,
        error: "Actions API returned an invalid response.",
        code: "invalid_response",
        status: response.status,
      };
    }

    return { ok: true, data: payload as { data: HumanRequiredActionRecord } };
  } catch {
    return {
      ok: false,
      error: "Could not reach the actions API.",
      code: "network_error",
    };
  }
}
