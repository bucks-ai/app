import type { SandboxStatus } from "@/types/database";

export type { SandboxStatus };

// Client-safe (no server imports) shared field metadata so src/lib/sandbox.ts
// and the client-side sandbox-status UI agree on field keys and labels.
export type SandboxFieldKey =
  | "repo_full_name"
  | "vercel_project_id"
  | "github_token_secret_name"
  | "vercel_token_secret_name";

export const SANDBOX_FIELDS: readonly SandboxFieldKey[] = [
  "repo_full_name",
  "vercel_project_id",
  "github_token_secret_name",
  "vercel_token_secret_name",
];

export const SANDBOX_FIELD_LABELS: Record<SandboxFieldKey, string> = {
  repo_full_name: "GitHub repository",
  vercel_project_id: "Vercel project",
  github_token_secret_name: "GitHub token (secret name)",
  vercel_token_secret_name: "Vercel token (secret name)",
};

export type SandboxFieldView = {
  field: SandboxFieldKey;
  label: string;
  configured: boolean;
  // The stored NAME (repo name, project id, or secret name) — never a
  // secret value, since business_sandbox never stores one.
  value: string | null;
};

export type SandboxConfigView = {
  status: SandboxStatus;
  fields: SandboxFieldView[];
  updatedAt: string | null;
};

export type SandboxConfigResponse = {
  sandbox: SandboxConfigView;
};

export type SetSandboxConfigBody = Partial<Record<SandboxFieldKey, string>>;
