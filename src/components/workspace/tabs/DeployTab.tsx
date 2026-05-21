import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { DeploymentStatusCard } from "@/components/deployment/DeploymentStatusCard";
import { DeploymentExecutionPanel } from "@/components/vercel/DeploymentExecutionPanel";

type DeployTabProps = {
  business: DashboardBusiness;
};

export function DeployTab({ business }: DeployTabProps) {
  return (
    <div className="space-y-5">
      <DeploymentStatusCard
        businessId={business.id}
        initialProject={business.vercelProject ?? null}
      />
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
