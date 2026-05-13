// Types for GitHub repository creation and management.
// Used by src/lib/github/* and src/app/api/github/create-repo/route.ts.
// All GitHub operations are server-side only — never import from client components.

export type GitHubRepoVisibility = "private" | "public";

// Input to createGitHubRepository
export interface CreateGitHubRepoInput {
  name: string;
  description?: string;
  visibility: GitHubRepoVisibility;
  owner?: string;
}

// Minimal shape of the GitHub API response for a repository
export interface GitHubRepoRecord {
  id: number;
  name: string;
  full_name: string;
  owner: { login: string };
  html_url: string;
  clone_url: string;
  ssh_url: string;
  private: boolean;
  description: string | null;
  created_at: string;
}

// Result returned by createGitHubRepository
export interface CreateGitHubRepoResult {
  repoUrl: string;
  fullName: string;
  owner: string;
  name: string;
  repoId: number;
  cloneUrl: string;
  sshUrl: string;
  private: boolean;
}

// Input for creating or updating a single file in a repo
export interface GitHubFileTemplate {
  path: string;
  content: string;
  message: string;
}
