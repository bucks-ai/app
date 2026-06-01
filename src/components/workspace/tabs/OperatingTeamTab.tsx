import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { OperatingTeamPanel } from "@/components/agents/OperatingTeamPanel";
import { WorkspaceSectionHeader } from "@/components/workspace/WorkspaceSectionHeader";

type OperatingTeamTabProps = {
  business: DashboardBusiness;
};

export function OperatingTeamTab({ business }: OperatingTeamTabProps) {
  return (
    <div>
      <WorkspaceSectionHeader
        eyebrow="Team"
        title="Operating team coverage and run history."
        description="See agent readiness, blocked dependencies, monitoring coverage, and recent run signals across the MVP operating graph."
      />
      <OperatingTeamPanel businessId={business.id} />
    </div>
  );
}
