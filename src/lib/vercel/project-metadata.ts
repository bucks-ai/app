// Server-side helper for reading Vercel project metadata persisted in agent_activity_logs.
// Project info is stored in the metadata column of the vercel_project_created activity log.

import { createSupabaseServerClient } from "@/lib/supabase/server";

export interface VercelProjectMetadata {
  vercelProjectId: string;
  vercelProjectName: string;
  vercelDashboardUrl: string;
  vercelDeploymentUrl?: string;
  gitRepoFullName?: string;
  productionBranch?: string;
  warnings?: string[];
  createdAt: string;
  activityLogId: string;
}

type Result<T> =
  | { data: T; error: null }
  | { data: null; error: string };

export async function getLatestVercelProjectForBusiness(
  businessId: string
): Promise<Result<VercelProjectMetadata>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) {
    return { data: null, error: "Supabase is not configured." };
  }

  const { data, error } = await supabase
    .from("agent_activity_logs")
    .select("id, metadata, created_at")
    .eq("business_id", businessId)
    .eq("activity_type", "vercel_project_created")
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (error || !data) {
    return { data: null, error: "No Vercel project found for this business." };
  }

  const row = data as { id: string; metadata: Record<string, unknown>; created_at: string };
  const meta = row.metadata;

  const warnings = Array.isArray(meta.warnings)
    ? (meta.warnings as string[])
    : undefined;

  return {
    data: {
      vercelProjectId: String(meta.vercelProjectId ?? ""),
      vercelProjectName: String(meta.vercelProjectName ?? ""),
      vercelDashboardUrl: String(meta.vercelDashboardUrl ?? ""),
      vercelDeploymentUrl: meta.vercelDeploymentUrl
        ? String(meta.vercelDeploymentUrl)
        : undefined,
      gitRepoFullName: meta.gitRepoFullName ? String(meta.gitRepoFullName) : undefined,
      productionBranch: meta.productionBranch ? String(meta.productionBranch) : undefined,
      warnings,
      createdAt: row.created_at,
      activityLogId: row.id,
    },
    error: null,
  };
}
