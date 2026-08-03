// Client-side fetch helpers for the Execute button
// (POST/GET /api/businesses/[id]/execute). Mirrors src/lib/approval-client.ts.

import type { MissionRecord, MissionTaskRecord } from "@/types/database";

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

export type ExecuteClientResult<T> = ApiSuccess<T> | ApiFailure;

const API_UNAVAILABLE = "Execute API not available yet. Merge backend branch first.";

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

async function requestJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<ExecuteClientResult<T>> {
  try {
    const response = await fetch(input, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });

    const payload = await readJson(response);

    if (response.status === 404 || response.status === 405) {
      return { ok: false, error: API_UNAVAILABLE, code: "api_unavailable", status: response.status };
    }

    if (!response.ok) {
      return {
        ok: false,
        error: getErrorMessage(payload, "Execute request failed."),
        code: "request_failed",
        status: response.status,
      };
    }

    if (!isRecord(payload)) {
      return { ok: false, error: "Execute API returned an invalid response.", code: "invalid_response", status: response.status };
    }

    return { ok: true, data: payload as T };
  } catch {
    return { ok: false, error: "Could not reach the execute API.", code: "network_error" };
  }
}

export async function fetchLatestMission(
  businessId: string
): Promise<ExecuteClientResult<{ data: { mission: MissionRecord | null } }>> {
  return requestJson<{ data: { mission: MissionRecord | null } }>(
    `/api/businesses/${encodeURIComponent(businessId)}/execute`
  );
}

export async function executeBusiness(
  businessId: string
): Promise<ExecuteClientResult<{ data: { mission: MissionRecord; tasks: MissionTaskRecord[] } }>> {
  return requestJson<{ data: { mission: MissionRecord; tasks: MissionTaskRecord[] } }>(
    `/api/businesses/${encodeURIComponent(businessId)}/execute`,
    { method: "POST" }
  );
}
