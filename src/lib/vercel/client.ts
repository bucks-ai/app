// Server-side Vercel REST API client.
// All functions require VERCEL_TOKEN in the environment.
// Never import from client components.

import { getVercelEnv } from "@/lib/vercel/env";
import type {
  CreateVercelProjectInput,
  VercelProjectRecord,
  VercelDeploymentRecord,
  CreateVercelProjectResult,
  VercelEnvironmentVariableInput,
} from "@/types/vercel";

const VERCEL_API_BASE = "https://api.vercel.com";

function vercelHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

// Append ?teamId=... when VERCEL_TEAM_ID is set
function withTeam(path: string, teamId: string | undefined): string {
  if (!teamId) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}teamId=${encodeURIComponent(teamId)}`;
}

// Sanitize a string into a valid Vercel project name:
// lowercase, alphanumeric + hyphens only, max 52 chars, no leading/trailing hyphens
export function sanitizeVercelProjectName(raw: string): string {
  return raw
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 52);
}

// ---------------------------------------------------------------------------
// Authenticated user
// ---------------------------------------------------------------------------

export interface VercelUser {
  id: string;
  email: string;
  username: string;
  name: string | null;
}

export async function getVercelUser(): Promise<VercelUser> {
  const { token } = getVercelEnv();

  const res = await fetch(`${VERCEL_API_BASE}/v2/user`, {
    headers: vercelHeaders(token),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Vercel /v2/user failed (${res.status}): ${body}`);
  }

  const data = (await res.json()) as { user: VercelUser };
  return data.user;
}

// ---------------------------------------------------------------------------
// Create project
// ---------------------------------------------------------------------------

export async function createVercelProject(
  input: CreateVercelProjectInput
): Promise<VercelProjectRecord> {
  const { token, teamId } = getVercelEnv();

  const body: Record<string, unknown> = {
    name: input.name,
    framework: input.framework ?? "nextjs",
    publicSource: input.publicSource ?? false,
  };

  if (input.gitRepository) {
    body.gitRepository = {
      type: input.gitRepository.type,
      repo: input.gitRepository.repo,
    };
  }

  if (input.rootDirectory) body.rootDirectory = input.rootDirectory;
  if (input.buildCommand) body.buildCommand = input.buildCommand;
  if (input.outputDirectory) body.outputDirectory = input.outputDirectory;
  if (input.installCommand) body.installCommand = input.installCommand;

  const url = withTeam(`${VERCEL_API_BASE}/v10/projects`, teamId);

  const res = await fetch(url, {
    method: "POST",
    headers: vercelHeaders(token),
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`Vercel project creation failed (${res.status}): ${errBody}`);
  }

  return (await res.json()) as VercelProjectRecord;
}

// ---------------------------------------------------------------------------
// Get project
// ---------------------------------------------------------------------------

export async function getVercelProject(input: {
  projectId: string;
}): Promise<VercelProjectRecord> {
  const { token, teamId } = getVercelEnv();

  const url = withTeam(
    `${VERCEL_API_BASE}/v9/projects/${encodeURIComponent(input.projectId)}`,
    teamId
  );

  const res = await fetch(url, {
    headers: vercelHeaders(token),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Vercel getProject failed (${res.status}): ${body}`);
  }

  return (await res.json()) as VercelProjectRecord;
}

// ---------------------------------------------------------------------------
// Create environment variables
// ---------------------------------------------------------------------------

export async function createVercelEnvironmentVariables(input: {
  projectId: string;
  envVars: VercelEnvironmentVariableInput[];
}): Promise<void> {
  const { token, teamId } = getVercelEnv();

  const url = withTeam(
    `${VERCEL_API_BASE}/v10/projects/${encodeURIComponent(input.projectId)}/env`,
    teamId
  );

  const res = await fetch(url, {
    method: "POST",
    headers: vercelHeaders(token),
    body: JSON.stringify(input.envVars),
  });

  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`Vercel env var creation failed (${res.status}): ${errBody}`);
  }
}

// ---------------------------------------------------------------------------
// List deployments
// ---------------------------------------------------------------------------

export async function listVercelDeployments(input: {
  projectId: string;
  limit?: number;
}): Promise<VercelDeploymentRecord[]> {
  const { token, teamId } = getVercelEnv();

  const params = new URLSearchParams({ projectId: input.projectId, limit: String(input.limit ?? 5) });
  if (teamId) params.set("teamId", teamId);

  const url = `${VERCEL_API_BASE}/v6/deployments?${params.toString()}`;

  const res = await fetch(url, {
    headers: vercelHeaders(token),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Vercel listDeployments failed (${res.status}): ${body}`);
  }

  const data = (await res.json()) as { deployments: VercelDeploymentRecord[] };
  return data.deployments ?? [];
}

// ---------------------------------------------------------------------------
// Trigger deployment from git (best-effort)
// Vercel auto-deploys when GitHub is linked and a push occurs.
// This creates an explicit deployment from the latest git commit when possible.
// Returns a warning string if the trigger could not be completed reliably.
// ---------------------------------------------------------------------------

export async function triggerVercelDeploymentIfSupported(input: {
  projectId: string;
  gitRepoFullName: string;
  productionBranch?: string;
}): Promise<{ deploymentUrl?: string; warning?: string }> {
  const { token, teamId } = getVercelEnv();

  const ref = input.productionBranch ?? "main";

  const body: Record<string, unknown> = {
    name: input.projectId,
    gitSource: {
      type: "github",
      repo: input.gitRepoFullName,
      ref,
    },
    target: "production",
  };

  const url = withTeam(`${VERCEL_API_BASE}/v13/deployments`, teamId);

  const res = await fetch(url, {
    method: "POST",
    headers: vercelHeaders(token),
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errBody = await res.text();
    // Deployment trigger failure is non-fatal — project was created successfully
    return {
      warning: `Project created but deployment trigger failed (${res.status}): ${errBody}. The project will deploy automatically on the next git push.`,
    };
  }

  const data = (await res.json()) as { url?: string; id?: string };
  const deploymentUrl = data.url ? `https://${data.url}` : undefined;
  return { deploymentUrl };
}

// ---------------------------------------------------------------------------
// High-level: create project + env vars + optional deployment trigger
// ---------------------------------------------------------------------------

export async function createVercelProjectWithSetup(input: {
  businessId: string;
  projectName: string;
  gitRepoFullName: string;
  createDeployment?: boolean;
}): Promise<CreateVercelProjectResult> {
  const warnings: string[] = [];

  // Create the project
  const project = await createVercelProject({
    name: input.projectName,
    framework: "nextjs",
    gitRepository: {
      type: "github",
      repo: input.gitRepoFullName,
    },
  });

  const projectId = project.id;
  const projectName = project.name;
  const dashboardUrl = `https://vercel.com/dashboard/${encodeURIComponent(projectName)}`;

  // Set a non-secret public env var identifying this business
  try {
    await createVercelEnvironmentVariables({
      projectId,
      envVars: [
        {
          key: "NEXT_PUBLIC_BUCKS_AI_BUSINESS_ID",
          value: input.businessId,
          type: "plain",
          target: ["production", "preview", "development"],
        },
      ],
    });
  } catch (e) {
    warnings.push(
      `Env var NEXT_PUBLIC_BUCKS_AI_BUSINESS_ID not set: ${e instanceof Error ? e.message : String(e)}`
    );
  }

  // Determine production branch from link metadata
  const productionBranch = project.link?.productionBranch ?? "main";
  const gitRepoFullName = project.link?.repo ?? input.gitRepoFullName;

  // Optionally trigger a deployment
  let deploymentUrl: string | undefined;
  if (input.createDeployment) {
    const deployResult = await triggerVercelDeploymentIfSupported({
      projectId,
      gitRepoFullName,
      productionBranch,
    });
    deploymentUrl = deployResult.deploymentUrl;
    if (deployResult.warning) warnings.push(deployResult.warning);
  }

  return {
    projectId,
    projectName,
    dashboardUrl,
    deploymentUrl,
    productionBranch,
    gitRepoFullName,
    warnings,
  };
}
