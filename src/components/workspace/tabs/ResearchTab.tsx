import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { ResearchWorkspacePanel } from "@/components/research/ResearchWorkspacePanel";

type ResearchTabProps = {
  business: DashboardBusiness;
};

export function ResearchTab({ business }: ResearchTabProps) {
  return <ResearchWorkspacePanel businessId={business.id} />;
}
