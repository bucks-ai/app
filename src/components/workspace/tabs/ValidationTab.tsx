import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { ValidationWorkspacePanel } from "@/components/validation/ValidationWorkspacePanel";

type ValidationTabProps = {
  business: DashboardBusiness;
};

export function ValidationTab({ business }: ValidationTabProps) {
  return <ValidationWorkspacePanel businessId={business.id} />;
}
