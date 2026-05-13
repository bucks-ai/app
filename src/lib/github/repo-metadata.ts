// Server-side helper for reading GitHub repo metadata persisted in agent_activity_logs.
// Repo info is stored in the metadata column of the github_repo_created activity log.

import { createSupabaseServerClient } from "@/lib/supabase/server";

export interface GitHubRepoMetadata {
  githubRepoUrl: string;
  githubRepoFullName: string;
  githubRepoId: number;
  githubCloneUrl: string;
  githubOwner: string;
  githubRepoName: string;
  createdAt: string;
  activityLogId: string;
}

type Result<T> =
  | { data: T; error: null }
  | { data: null; error: string };

export async function getLatestGitHubRepoForBusiness(
  businessId: string
): Promise<Result<GitHubRepoMetadata>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) {
    return { data: null, error: "Supabase is not configured." };
  }

  const { data, error } = await supabase
    .from("agent_activity_logs")
    .select("id, metadata, created_at")
    .eq("business_id", businessId)
    .eq("activity_type", "github_repo_created")
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (error || !data) {
    return { data: null, error: "No GitHub repo found for this business." };
  }

  const row = data as { id: string; metadata: Record<string, unknown>; created_at: string };
  const meta = row.metadata;

  return {
    data: {
      githubRepoUrl: String(meta.githubRepoUrl ?? ""),
      githubRepoFullName: String(meta.githubRepoFullName ?? ""),
      githubRepoId: Number(meta.githubRepoId ?? 0),
      githubCloneUrl: String(meta.githubCloneUrl ?? ""),
      githubOwner: String(meta.githubOwner ?? ""),
      githubRepoName: String(meta.githubRepoName ?? ""),
      createdAt: row.created_at,
      activityLogId: row.id,
    },
    error: null,
  };
}
