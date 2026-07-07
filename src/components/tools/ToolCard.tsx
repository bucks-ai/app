import type { RiskLevel, SetupStatus, ToolRegistryItem, ToolStatus } from "@/types/tools";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { RiskBadge, type RiskTone } from "@/components/ui/RiskBadge";
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

function getRiskTone(riskLevel: RiskLevel): RiskTone {
  switch (riskLevel) {
    case "Low":
      return "low";
    case "Medium":
      return "medium";
    case "High":
      return "high";
    case "Critical":
      return "critical";
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

/**
 * Fixed card anatomy, top to bottom: category + connection state,
 * mono tool name, risk row, purpose, permissions ledger, human gates.
 */
export function ToolCard({ tool }: { tool: ToolRegistryItem }) {
  const requirementBadges = [
    tool.requiresTermsAcceptance ? "Terms" : null,
    tool.requiresIdentityVerification ? "Identity" : null,
    tool.requiresPaymentSetup ? "Payment" : null,
  ].filter(Boolean) as string[];

  return (
    <OperatorPanel className="flex h-full flex-col p-5 sm:p-6">
      {/* header: identity + connection state */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <SectionLabel tone="muted">{tool.category}</SectionLabel>
          <h3 className="mt-2 font-mono text-lg font-semibold tracking-tight text-foreground">
            {tool.name}
          </h3>
        </div>
        <ToolStatusBadge
          label={tool.status}
          variant={getStatusVariant(tool.status)}
        />
      </div>

      {/* risk + setup row */}
      <div className="mt-4 flex flex-wrap gap-2">
        <RiskBadge level={getRiskTone(tool.riskLevel)} />
        <ToolStatusBadge
          label={tool.setupStatus}
          variant={getSetupVariant(tool.setupStatus)}
        />
        <ToolStatusBadge
          label={tool.canAiSetupFully ? "AI setup ready" : "Human step required"}
          variant={tool.canAiSetupFully ? "success" : "neutral"}
        />
      </div>

      <p className="mt-4 text-sm leading-6 text-secondary">{tool.purpose}</p>
      <p className="mt-2 text-sm leading-6 text-secondary">{tool.typicalUse}</p>

      {tool.requiresPaymentSetup || tool.category === "Payments" ? (
        <div className="mt-4 rounded-md border border-warning/25 bg-warning/10 px-3 py-2 text-sm leading-6 text-warning">
          Payment setup and terms remain founder-controlled.
        </div>
      ) : null}

      {/* permissions ledger — pinned to the bottom so card anatomy aligns */}
      <div aria-hidden className="min-h-5 flex-1" />
      <div className="grid gap-4 border-t border-border pt-5">
        <div>
          <SectionLabel tone="muted">Default permissions</SectionLabel>
          <ul className="mt-3 divide-y divide-border-subtle rounded-md border border-border-subtle bg-background">
            {tool.defaultPermissions.map((permission) => (
              <li
                key={permission}
                className="flex items-baseline gap-2.5 px-3 py-2 font-mono text-xs leading-5 text-secondary"
              >
                <span aria-hidden className="text-accent">
                  ▸
                </span>
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
                  className="rounded-md border-l-2 border-warning/60 bg-warning/10 px-3 py-2 text-sm leading-6 text-warning"
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
