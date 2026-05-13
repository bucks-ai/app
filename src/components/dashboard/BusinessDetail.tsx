import Link from "next/link";
import { ActivityLog } from "@/components/dashboard/ActivityLog";
import { HumanActionQueue } from "@/components/dashboard/HumanActionQueue";
import { ToolPermissionSummary } from "@/components/dashboard/ToolPermissionSummary";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { GitHubRepoCard } from "@/components/github/GitHubRepoCard";
import { GitHubRepoGate } from "@/components/github/GitHubRepoGate";
import { PermissionControlRoom } from "@/components/tools/PermissionControlRoom";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";
import { DeploymentExecutionPanel } from "@/components/vercel/DeploymentExecutionPanel";

type BusinessDetailProps = {
  business: DashboardBusiness;
};

function isApprovedGitHubPermission(business: DashboardBusiness) {
  const githubPermission = business.toolPermissions?.find(
    (permission) => permission.toolId === "github"
  );

  if (!githubPermission) return true;

  return (
    githubPermission.status === "approved" ||
    githubPermission.status === "approved_by_founder" ||
    githubPermission.status === "connected_demo" ||
    githubPermission.setupStatus === "ready_to_connect" ||
    githubPermission.setupStatus === "connected_demo"
  );
}

export function BusinessDetail({ business }: BusinessDetailProps) {
  const humanActions =
    business.humanActionItems ??
    business.humanActions.map((action) => ({
      title: action,
      business: business.name,
      reason: "This action requires founder approval before autonomous execution.",
      status: "Needs review",
    }));

  return (
    <div className="space-y-8">
      <Link
        href="/dashboard"
        className="inline-flex text-sm font-medium text-[#A5B4FC] transition-colors hover:text-[#C7D2FE]"
      >
        &lt;- Back to Mission Control
      </Link>

      <OperatorPanel className="p-6 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-3">
              <SectionLabel>{business.sourceLabel ?? "Saved build record"}</SectionLabel>
              <StatusPill label={business.status} variant={business.statusVariant} />
            </div>
            <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
              {business.name}
            </h1>
            <p className="mt-4 text-base leading-8 text-[#888888]">{business.overview}</p>
          </div>
          <div className="grid min-w-64 gap-3 rounded-lg border border-[#1C1C1C] bg-[#080808] p-4">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                Business type
              </p>
              <p className="mt-2 text-sm font-medium text-[#F0F0F0]">
                {business.businessType}
              </p>
            </div>
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                Goal
              </p>
              <p className="mt-2 text-sm leading-6 text-[#D4D4D4]">{business.goal}</p>
            </div>
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                Created
              </p>
              <p className="mt-2 text-sm leading-6 text-[#D4D4D4]">{business.created}</p>
            </div>
          </div>
        </div>
      </OperatorPanel>

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <OperatorPanel className="p-6">
          <SectionLabel>Latest blueprint summary</SectionLabel>
          <p className="mt-4 text-sm leading-7 text-[#D4D4D4]">
            {business.blueprintSummary}
          </p>
        </OperatorPanel>

        <OperatorPanel className="p-6" elevated>
          <SectionLabel tone="warning">Human-required actions</SectionLabel>
          <div className="mt-5">
            {humanActions.length > 0 ? (
              <HumanActionQueue actions={humanActions} />
            ) : (
              <p className="rounded-md border border-[#F59E0B]/25 bg-[#F59E0B]/10 p-4 text-sm leading-6 text-[#FDE68A]">
                No pending human-required actions are attached to this business.
              </p>
            )}
          </div>
        </OperatorPanel>
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <OperatorPanel className="p-6 xl:col-span-1">
          <SectionLabel>Next autonomous actions</SectionLabel>
          <ul className="mt-5 space-y-3">
            {business.nextActions.length > 0 ? (
              business.nextActions.map((action) => (
                <li
                  key={action}
                  className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4 text-sm leading-6 text-[#D4D4D4]"
                >
                  {action}
                </li>
              ))
            ) : (
              <li className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4 text-sm leading-6 text-[#888888]">
                No autonomous action queue was found in the latest blueprint.
              </li>
            )}
          </ul>
        </OperatorPanel>

        <OperatorPanel className="p-6 xl:col-span-1">
          <SectionLabel>Activity log</SectionLabel>
          <div className="mt-5">
            {business.activity.length > 0 ? (
              <ActivityLog items={business.activity} />
            ) : (
              <p className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4 text-sm leading-6 text-[#888888]">
                Activity logs will appear as bucks.ai works on this project.
              </p>
            )}
          </div>
        </OperatorPanel>

        <OperatorPanel className="p-6 xl:col-span-1">
          <SectionLabel>Tool permissions</SectionLabel>
          <div className="mt-5">
            {business.permissions.length > 0 ? (
              <ToolPermissionSummary permissions={business.permissions} />
            ) : (
              <p className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4 text-sm leading-6 text-[#888888]">
                No suggested tool permissions were found in the latest blueprint.
              </p>
            )}
          </div>
        </OperatorPanel>
      </section>

      <div id="tool-setup-queue" className="scroll-mt-28">
        <PermissionControlRoom businessId={business.id} businessName={business.name} />
      </div>

      <OperatorPanel
        id="repository-execution"
        className="scroll-mt-28 p-6 shadow-[0_30px_120px_rgba(0,0,0,0.34)] sm:p-8"
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-3">
              <SectionLabel>Repository Execution</SectionLabel>
              <StatusPill label="Controlled external action" variant="warning" />
            </div>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-[#F0F0F0]">
              GitHub repository creation
            </h2>
            <p className="mt-3 text-sm leading-7 text-[#888888] sm:text-base">
              Create a private GitHub repo only after GitHub is approved in the
              setup queue. This is the first real external asset bucks.ai can
              create for a saved business.
            </p>
          </div>
        </div>

        <div className="mt-6">
          {isApprovedGitHubPermission(business) ? (
            <GitHubRepoCard
              businessId={business.id}
              businessName={business.name}
              oneLineIdea={business.oneLineIdea ?? business.overview}
              existingRepo={business.githubRepo ?? null}
            />
          ) : (
            <GitHubRepoGate />
          )}
        </div>
      </OperatorPanel>

      <DeploymentExecutionPanel
        businessId={business.id}
        businessName={business.name}
        oneLineIdea={business.oneLineIdea ?? business.overview}
        activityLogs={business.activityLogs}
        toolPermissions={business.toolPermissions}
        existingGitHubRepo={business.githubRepo ?? null}
        existingVercelProject={business.vercelProject ?? null}
      />
    </div>
  );
}
