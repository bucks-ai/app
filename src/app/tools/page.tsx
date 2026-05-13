import type { Metadata } from "next";
import { ToolRegistryPage } from "@/components/tools/ToolRegistryPage";
import { getCurrentUser, getUserBusinesses } from "@/lib/projects";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import type { BusinessPermissionOption } from "@/types/tool-permission-ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Tool Registry | bucks.ai",
  description:
    "Review bucks.ai's preferred tool stack, extended registry, risk and setup status, and the default autonomy constitution.",
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

export default async function ToolsPage() {
  if (!hasSupabaseEnv()) {
    return (
      <ToolRegistryPage
        permissionAuthState="supabase_missing"
        permissionLoadError="Supabase environment variables are not configured, so saved business selection is unavailable."
      />
    );
  }

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return <ToolRegistryPage permissionAuthState="signed_out" />;
  }

  const businessesResult = await getUserBusinesses();
  if (businessesResult.error || !businessesResult.data) {
    return (
      <ToolRegistryPage
        permissionAuthState="load_failed"
        permissionLoadError={businessesResult.error}
      />
    );
  }

  const businesses: BusinessPermissionOption[] = businessesResult.data.map(
    (business) => ({
      id: business.id,
      name: business.idea_name,
      status: business.status,
      createdLabel: formatDate(business.created_at),
    })
  );

  return (
    <ToolRegistryPage
      permissionAuthState="signed_in"
      permissionBusinesses={businesses}
    />
  );
}
