import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { DeploymentExecutionPanel } from "@/components/vercel/DeploymentExecutionPanel";

type DeployTabProps = {
  business: DashboardBusiness;
};

export function DeployTab({ business }: DeployTabProps) {
  return (
    <div>
      <DeploymentExecutionPanel
        businessId={business.id}
        businessName={business.name}
        oneLineIdea={business.oneLineIdea ?? business.overview}
        activityLogs={business.activityLogs}
        toolPermissions={business.toolPermissions}
        existingGitHubRepo={business.githubRepo ?? null}
        existingVercelProject={business.vercelProject ?? null}
      />
    </div>
  );
}
