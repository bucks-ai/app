import type { RiskLevel, SetupStatus, ToolRegistryItem, ToolStatus } from "@/types/tools";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { ToolStatusBadge } from "@/components/tools/ToolStatusBadge";

function getStatusVariant(status: ToolStatus) {
  switch (status) {
    case "Preferred":
      return "preferred" as const;
    case "Approved":
      return "approved" as const;
    case "External Approval Required":
      return "external" as const;
    case "Blocked":
      return "blocked" as const;
    case "Human Only":
      return "human" as const;
  }
}

function getRiskVariant(riskLevel: RiskLevel) {
  switch (riskLevel) {
    case "Low":
      return "low" as const;
    case "Medium":
      return "medium" as const;
    case "High":
      return "high" as const;
    case "Critical":
      return "critical" as const;
  }
}

function getSetupVariant(setupStatus: SetupStatus) {
  switch (setupStatus) {
    case "Fully Completed":
      return "success" as const;
    case "Awaiting Human Legal Step":
      return "warning" as const;
    case "Requires Identity Or Payment Step":
      return "warning" as const;
    case "Blocked By Verification":
      return "danger" as const;
    case "Rejected By Policy":
      return "danger" as const;
    case "Not Connected":
      return "neutral" as const;
  }
}

export function ToolCard({ tool }: { tool: ToolRegistryItem }) {
  const requirementBadges = [
    tool.requiresTermsAcceptance ? "Terms" : null,
    tool.requiresIdentityVerification ? "Identity" : null,
    tool.requiresPaymentSetup ? "Payment" : null,
  ].filter(Boolean) as string[];

  return (
    <OperatorPanel className="flex h-full flex-col p-5 shadow-[0_24px_80px_rgba(0,0,0,0.3)] sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <SectionLabel tone="muted">{tool.category}</SectionLabel>
          <h3 className="mt-2 text-xl font-semibold text-[#F0F0F0]">{tool.name}</h3>
        </div>
        <ToolStatusBadge
          label={tool.status}
          variant={getStatusVariant(tool.status)}
        />
      </div>

      <p className="mt-4 text-sm leading-6 text-[#D4D4D4]">{tool.purpose}</p>
      <p className="mt-3 text-sm leading-6 text-[#888888]">{tool.typicalUse}</p>

      {tool.requiresPaymentSetup || tool.category === "Payments" ? (
        <div className="mt-4 rounded-md border border-[#F59E0B]/25 bg-[#F59E0B]/10 px-3 py-2 text-sm leading-6 text-[#FDE68A]">
          Payment setup and terms remain founder-controlled.
        </div>
      ) : null}

      <div className="mt-5 flex flex-wrap gap-2">
        <ToolStatusBadge
          label={`${tool.riskLevel} risk`}
          variant={getRiskVariant(tool.riskLevel)}
        />
        <ToolStatusBadge
          label={tool.setupStatus}
          variant={getSetupVariant(tool.setupStatus)}
        />
        <ToolStatusBadge
          label={tool.canAiSetupFully ? "AI setup ready" : "Human step required"}
          variant={tool.canAiSetupFully ? "success" : "neutral"}
        />
      </div>

      <div className="mt-6 grid gap-4 border-t border-[#1C1C1C] pt-5">
        <div>
          <SectionLabel tone="muted">Default permissions</SectionLabel>
          <ul className="mt-3 space-y-2">
            {tool.defaultPermissions.map((permission) => (
              <li
                key={permission}
                className="rounded-md border border-[#1C1C1C] bg-[#080808] px-3 py-2 text-sm text-[#D4D4D4]"
              >
                {permission}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <SectionLabel tone="muted">Human gates</SectionLabel>
          <div className="mt-3 flex flex-wrap gap-2">
            {requirementBadges.length > 0 ? (
              requirementBadges.map((requirement) => (
                <ToolStatusBadge
                  key={requirement}
                  label={requirement}
                  variant="warning"
                />
              ))
            ) : (
              <ToolStatusBadge label="None by default" variant="success" />
            )}
          </div>
        </div>

        {tool.humanOnlyReasons.length > 0 ? (
          <div>
            <SectionLabel tone="warning">Human-only reasons</SectionLabel>
            <ul className="mt-3 space-y-2">
              {tool.humanOnlyReasons.map((reason) => (
                <li
                  key={reason}
                  className="rounded-md border border-[#F59E0B]/25 bg-[#F59E0B]/10 px-3 py-2 text-sm leading-6 text-[#FDE68A]"
                >
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </OperatorPanel>
  );
}
