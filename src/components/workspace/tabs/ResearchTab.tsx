import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { ResearchWorkspacePanel } from "@/components/research/ResearchWorkspacePanel";
import { WorkspaceSectionHeader } from "@/components/workspace/WorkspaceSectionHeader";

type ResearchTabProps = {
  business: DashboardBusiness;
};

export function ResearchTab({ business }: ResearchTabProps) {
  return (
    <div>
      <WorkspaceSectionHeader
        eyebrow="Research"
        title="Map the market before build work compounds."
        description="Review opportunity score, customer segments, competitors, monetization, risks, hypotheses, and evidence from one focused workspace."
      />
      <ResearchWorkspacePanel businessId={business.id} />
    </div>
  );
}
