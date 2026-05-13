import type {
  GitHubCreateRepoInput,
  GitHubCreateRepoResponse,
  GitHubRepoResult,
} from "@/types/github-ui";

const GITHUB_API_UNAVAILABLE =
  "GitHub backend route is not available yet. Merge backend branch first.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function readBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
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

function normalizeRepoResult(value: unknown): GitHubRepoResult | null {
  if (!isRecord(value)) return null;

  const repoUrl = asString(value.repoUrl) ?? asString(value.html_url);
  const fullName = asString(value.fullName) ?? asString(value.full_name);
  const owner = asString(value.owner);
  const name = asString(value.name);
  const isPrivate = readBoolean(value.private);

  if (!repoUrl || !fullName || !owner || !name || isPrivate === null) {
    return null;
  }

  return {
    repoUrl,
    fullName,
    owner,
    name,
    private: isPrivate,
  };
}

function normalizeErrorCode(status: number, payload: unknown): string {
  if (isRecord(payload) && typeof payload.code === "string" && payload.code.trim()) {
    return payload.code;
  }

  if (status === 401 || status === 403) return "permission_required";
  if (status === 404 || status === 405) return "api_unavailable";
  return "request_failed";
}

function friendlyError(status: number, code: string, payload: unknown) {
  const rawError =
    isRecord(payload) && typeof payload.error === "string" && payload.error.trim()
      ? payload.error
      : null;

  if (code === "api_unavailable" || status === 404 || status === 405) {
    return GITHUB_API_UNAVAILABLE;
  }

  if (
    code === "github_token_missing" ||
    code === "token_missing" ||
    code.toLowerCase().includes("token") ||
    rawError?.toLowerCase().includes("token")
  ) {
    return "GitHub token is not configured on the server.";
  }

  if (
    code === "permission_required" ||
    code === "permission_missing" ||
    code === "github_permission_required" ||
    status === 401 ||
    status === 403
  ) {
    return "Approve GitHub in Tool Setup Queue first.";
  }

  return rawError ?? "GitHub repo creation failed. No external assets were created.";
}

export async function createGitHubRepo(
  input: GitHubCreateRepoInput
): Promise<GitHubCreateRepoResponse> {
  try {
    const response = await fetch("/api/github/create-repo", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(input),
    });

    const payload = await readJson(response);
    const code = normalizeErrorCode(response.status, payload);

    if (!response.ok) {
      return {
        ok: false,
        code,
        error: friendlyError(response.status, code, payload),
      };
    }

    if (isRecord(payload) && payload.ok === false) {
      const failureCode = normalizeErrorCode(response.status, payload);

      return {
        ok: false,
        code: failureCode,
        error: friendlyError(response.status, failureCode, payload),
      };
    }

    if (!isRecord(payload) || payload.ok !== true) {
      return {
        ok: false,
        code: "invalid_response",
        error: "GitHub backend returned an invalid response.",
      };
    }

    const dataSource = isRecord(payload.data) ? payload.data : null;
    const data = normalizeRepoResult(dataSource);

    if (!data) {
      return {
        ok: false,
        code: "invalid_response",
        error: "GitHub backend returned repo data in an unexpected shape.",
      };
    }

    const warning =
      typeof payload.warning === "string" && payload.warning.trim()
        ? payload.warning
        : undefined;

    return {
      ok: true,
      data,
      ...(warning ? { warning } : {}),
    };
  } catch {
    return {
      ok: false,
      code: "network_error",
      error: "Could not reach the GitHub repo creation route.",
    };
  }
}
