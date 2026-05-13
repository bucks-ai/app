"use client";

import { PermissionActionBar } from "@/components/tools/PermissionActionBar";
import { PermissionStatusPill } from "@/components/tools/PermissionStatusPill";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import type {
  ToolPermissionAction,
  ToolPermissionView,
} from "@/types/tool-permission-ui";

type PermissionToolCardProps = {
  permission: ToolPermissionView;
  readOnly?: boolean;
  busyAction?: ToolPermissionAction | null;
  onAction: (id: string, action: ToolPermissionAction) => void;
};

const riskClasses = {
  low: "border-[#22C55E]/25 bg-[#22C55E]/10 text-[#86EFAC]",
  medium: "border-[#F59E0B]/25 bg-[#F59E0B]/10 text-[#FDE68A]",
  high: "border-[#F59E0B]/35 bg-[#F59E0B]/10 text-[#FCD34D]",
  critical: "border-[#EF4444]/35 bg-[#EF4444]/10 text-[#FCA5A5]",
};

function formatRisk(risk: ToolPermissionView["riskLevel"]) {
  return `${risk.charAt(0).toUpperCase()}${risk.slice(1)} risk`;
}

export function PermissionToolCard({
  permission,
  readOnly = false,
  busyAction = null,
  onAction,
}: PermissionToolCardProps) {
  const requiresHumanControl =
    permission.requiresPaymentSetup ||
    permission.requiresIdentityVerification ||
    permission.requiresTermsAcceptance ||
    permission.status === "human_required" ||
    permission.riskLevel === "critical";

  return (
    <OperatorPanel className="flex min-w-0 flex-col p-5 shadow-[0_20px_70px_rgba(0,0,0,0.24)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <SectionLabel tone="muted">{permission.category ?? "Tool"}</SectionLabel>
          <h3 className="mt-2 break-words text-xl font-semibold text-[#F0F0F0]">
            {permission.toolName}
          </h3>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
          <PermissionStatusPill status={permission.status} />
          <span
            className={`inline-flex w-fit rounded-md border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.18em] ${riskClasses[permission.riskLevel]}`}
          >
            {formatRisk(permission.riskLevel)}
          </span>
        </div>
      </div>

      <p className="mt-4 text-sm leading-6 text-[#D4D4D4]">
        {permission.purpose}
      </p>
      {permission.typicalUse ? (
        <p className="mt-3 text-sm leading-6 text-[#888888]">
          {permission.typicalUse}
        </p>
      ) : null}

      {permission.status === "connected_demo" ? (
        <div className="mt-4 rounded-md border border-[#4F46E5]/30 bg-[#4F46E5]/10 px-3 py-2 text-sm leading-6 text-[#C7D2FE]">
          Demo connected. No real external account has been connected yet.
        </div>
      ) : null}

      {requiresHumanControl ? (
        <div className="mt-4 rounded-md border border-[#F59E0B]/30 bg-[#F59E0B]/10 px-3 py-2 text-sm leading-6 text-[#FDE68A]">
          Founder-controlled. Human approval required. bucks.ai cannot accept
          terms, enter payment data, or sign contracts.
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 border-t border-[#1C1C1C] pt-5 lg:grid-cols-2">
        <div>
          <SectionLabel tone="muted">Requested permissions</SectionLabel>
          <ul className="mt-3 space-y-2">
            {permission.permissions.length > 0 ? (
              permission.permissions.map((item) => (
                <li
                  key={item}
                  className="rounded-md border border-[#1C1C1C] bg-[#080808] px-3 py-2 text-sm leading-6 text-[#D4D4D4]"
                >
                  {item}
                </li>
              ))
            ) : (
              <li className="rounded-md border border-[#1C1C1C] bg-[#080808] px-3 py-2 text-sm leading-6 text-[#888888]">
                No permission scopes have been requested yet.
              </li>
            )}
          </ul>
        </div>

        <div>
          <SectionLabel tone="warning">Human gates</SectionLabel>
          <ul className="mt-3 space-y-2">
            {permission.humanOnlyReasons.length > 0 ? (
              permission.humanOnlyReasons.map((reason) => (
                <li
                  key={reason}
                  className="rounded-md border border-[#F59E0B]/25 bg-[#F59E0B]/10 px-3 py-2 text-sm leading-6 text-[#FDE68A]"
                >
                  {reason}
                </li>
              ))
            ) : (
              <li className="rounded-md border border-[#1C1C1C] bg-[#080808] px-3 py-2 text-sm leading-6 text-[#888888]">
                No default human-only gate beyond founder review.
              </li>
            )}
          </ul>
        </div>
      </div>

      <div className="mt-5">
        {readOnly ? (
          <p className="rounded-md border border-[#1C1C1C] bg-[#080808] px-3 py-2 text-sm leading-6 text-[#888888]">
            Preview only. Select a saved business with the permission API
            available to update this tool.
          </p>
        ) : (
          <PermissionActionBar
            status={permission.status}
            busyAction={busyAction}
            onAction={(action) => onAction(permission.id, action)}
          />
        )}
      </div>
    </OperatorPanel>
  );
}
