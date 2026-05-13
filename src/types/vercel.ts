// Types for Vercel project creation and management.
// All Vercel operations are server-side only — never import from client components.

export type VercelProjectFramework =
  | "nextjs"
  | "create-react-app"
  | "vite"
  | "remix"
  | null;

// Input to createVercelProject
export interface CreateVercelProjectInput {
  name: string;
  framework?: VercelProjectFramework;
  gitRepository?: {
    type: "github";
    repo: string; // full name, e.g. "owner/repo-name"
  };
  rootDirectory?: string;
  buildCommand?: string;
  outputDirectory?: string;
  installCommand?: string;
  publicSource?: boolean;
}

// Minimal shape of the Vercel API project response
export interface VercelProjectRecord {
  id: string;
  name: string;
  framework: string | null;
  link?: {
    type: string;
    repo: string;
    repoId?: number;
    org?: string;
    gitCredentialId?: string;
    productionBranch?: string;
  } | null;
  latestDeployments?: VercelDeploymentRecord[];
  createdAt?: number;
  updatedAt?: number;
}

// Minimal shape of a Vercel deployment
export interface VercelDeploymentRecord {
  uid: string;
  name: string;
  url: string;
  state: "BUILDING" | "ERROR" | "INITIALIZING" | "QUEUED" | "READY" | "CANCELED" | string;
  target?: "production" | "staging" | null;
  createdAt?: number;
  readyAt?: number;
  buildingAt?: number;
}

// Result returned by createVercelProject
export interface CreateVercelProjectResult {
  projectId: string;
  projectName: string;
  dashboardUrl: string;
  deploymentUrl?: string;
  productionBranch?: string;
  gitRepoFullName?: string;
  warnings: string[];
}

// Structured error from the Vercel API
export interface VercelApiError {
  code: string;
  message: string;
}

// Input for setting environment variables on a Vercel project
export interface VercelEnvironmentVariableInput {
  key: string;
  value: string;
  type: "plain" | "secret" | "encrypted";
  target: ("production" | "preview" | "development")[];
}
