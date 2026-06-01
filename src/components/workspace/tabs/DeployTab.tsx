import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { DeploymentStatusCard } from "@/components/deployment/DeploymentStatusCard";
import { DeploymentExecutionPanel } from "@/components/vercel/DeploymentExecutionPanel";
import { WorkspaceSectionHeader } from "@/components/workspace/WorkspaceSectionHeader";

type DeployTabProps = {
  business: DashboardBusiness;
};

export function DeployTab({ business }: DeployTabProps) {
  return (
    <div className="space-y-5">
      <WorkspaceSectionHeader
        eyebrow="Deploy"
        title="Deployment status and release controls."
        description="Keep Vercel status, project creation, scaffold preparation, and live-app links together without mixing them into the overview."
      />
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
