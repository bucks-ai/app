import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { OperatingTeamPanel } from "@/components/agents/OperatingTeamPanel";

type OperatingTeamTabProps = {
  business: DashboardBusiness;
};

export function OperatingTeamTab({ business }: OperatingTeamTabProps) {
  return <OperatingTeamPanel businessId={business.id} />;
}
