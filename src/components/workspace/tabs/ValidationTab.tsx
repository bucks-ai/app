import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { ValidationWorkspacePanel } from "@/components/validation/ValidationWorkspacePanel";
import { WorkspaceSectionHeader } from "@/components/workspace/WorkspaceSectionHeader";

type ValidationTabProps = {
  business: DashboardBusiness;
};

export function ValidationTab({ business }: ValidationTabProps) {
  return (
    <div>
      <WorkspaceSectionHeader
        eyebrow="Validation"
        title="Turn demand signals into operating decisions."
        description="Track personas, hypotheses, leads, and interview feedback without burying the next customer action."
      />
      <ValidationWorkspacePanel businessId={business.id} />
    </div>
  );
}
