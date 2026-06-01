import { PermissionControlRoom } from "@/components/tools/PermissionControlRoom";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { CompactToolQueue } from "@/components/workspace/CompactToolQueue";

type ToolsTabProps = {
  business: DashboardBusiness;
  businessId: string;
  businessName: string;
};

export function ToolsTab({ business, businessId, businessName }: ToolsTabProps) {
  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
              Compact approval queue
            </p>
            <h2 className="mt-1 text-lg font-semibold text-foreground">
              Tools waiting on setup decisions
            </h2>
          </div>
          <p className="max-w-sm text-xs leading-5 text-muted">
            Detail controls remain below; overview and rail stay compact.
          </p>
        </div>
        <CompactToolQueue business={business} full />
      </div>
      <PermissionControlRoom
        businessId={businessId}
        businessName={businessName}
      />
    </div>
  );
}
