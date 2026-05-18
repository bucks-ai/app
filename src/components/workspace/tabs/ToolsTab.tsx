import { PermissionControlRoom } from "@/components/tools/PermissionControlRoom";

type ToolsTabProps = {
  businessId: string;
  businessName: string;
};

export function ToolsTab({ businessId, businessName }: ToolsTabProps) {
  return (
    <div>
      <PermissionControlRoom
        businessId={businessId}
        businessName={businessName}
      />
    </div>
  );
}
