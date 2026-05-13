import { StatusPill } from "@/components/ui/StatusPill";
import type { ToolPermission } from "@/components/dashboard/mock-data";

type ToolPermissionSummaryProps = {
  permissions: ToolPermission[];
  className?: string;
};

export function ToolPermissionSummary({
  permissions,
  className = "space-y-3",
}: ToolPermissionSummaryProps) {
  return (
    <div className={className}>
      {permissions.map((permission) => (
        <div
          key={`${permission.tool}-${permission.access}`}
          className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h3 className="text-sm font-semibold text-[#F0F0F0]">{permission.tool}</h3>
            <StatusPill label={permission.access} variant={permission.tone} />
          </div>
          <p className="mt-3 text-sm leading-6 text-[#888888]">{permission.note}</p>
        </div>
      ))}
    </div>
  );
}
