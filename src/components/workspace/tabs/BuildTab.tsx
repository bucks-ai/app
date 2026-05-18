import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { GitHubRepoCard } from "@/components/github/GitHubRepoCard";
import { GitHubRepoGate } from "@/components/github/GitHubRepoGate";

type BuildTabProps = {
  business: DashboardBusiness;
};

function isApprovedGitHub(business: DashboardBusiness) {
  const perm = business.toolPermissions?.find((p) => p.toolId === "github");
  if (!perm) return true;
  return (
    perm.status === "approved" ||
    perm.status === "approved_by_founder" ||
    perm.status === "connected_demo" ||
    perm.setupStatus === "ready_to_connect" ||
    perm.setupStatus === "connected_demo"
  );
}

type StepStatus = "complete" | "active" | "pending";

function StepRow({
  index,
  label,
  status,
  children,
}: {
  index: number;
  label: string;
  status: StepStatus;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-lg border bg-[#0F0F0F] ${
        status === "active"
          ? "border-[#4F46E5]/30"
          : status === "complete"
            ? "border-[#22C55E]/20"
            : "border-[#1C1C1C]"
      }`}
    >
      <div className="flex items-center gap-3 p-4">
        <span
          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
            status === "complete"
              ? "bg-[#22C55E] text-[#0A0A0A]"
              : status === "active"
                ? "bg-[#4F46E5] text-[#F0F0F0]"
                : "bg-[#1C1C1C] text-[#444]"
          }`}
        >
          {status === "complete" ? "✓" : index}
        </span>
        <p
          className={`text-sm font-medium ${
            status === "pending" ? "text-[#444]" : "text-[#F0F0F0]"
          }`}
        >
          {label}
        </p>
        {status === "active" ? (
          <span className="ml-auto rounded border border-[#4F46E5]/30 bg-[#4F46E5]/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[#A5B4FC]">
            Active
          </span>
        ) : null}
      </div>
      {status === "active" && children ? (
        <div className="border-t border-[#1C1C1C] p-4">{children}</div>
      ) : null}
    </div>
  );
}

export function BuildTab({ business }: BuildTabProps) {
  const githubApproved = isApprovedGitHub(business);
  const hasRepo = Boolean(business.githubRepo);
  const scaffoldReady = hasRepo;

  const step1Status: StepStatus = githubApproved ? "complete" : "active";
  const step2Status: StepStatus = !githubApproved
    ? "pending"
    : hasRepo
      ? "complete"
      : "active";
  const step3Status: StepStatus = !hasRepo ? "pending" : scaffoldReady ? "active" : "pending";

  return (
    <div className="space-y-2">
      <StepRow index={1} label="GitHub approved" status={step1Status}>
        <GitHubRepoGate />
      </StepRow>

      <StepRow index={2} label="Repository created" status={step2Status}>
        <GitHubRepoCard
          businessId={business.id}
          businessName={business.name}
          oneLineIdea={business.oneLineIdea ?? business.overview}
          existingRepo={business.githubRepo ?? null}
        />
      </StepRow>

      <StepRow index={3} label="Scaffold prepared" status={step3Status}>
        {hasRepo ? (
          <div className="rounded border border-[#1C1C1C] bg-[#080808] p-4">
            <p className="text-sm text-[#888]">
              Repository is ready. Scaffold preparation follows repository creation.
            </p>
            {business.githubRepo ? (
              <a
                href={business.githubRepo.repoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-widest text-[#A5B4FC] transition-colors hover:text-[#C7D2FE]"
              >
                View repo
              </a>
            ) : null}
          </div>
        ) : null}
      </StepRow>
    </div>
  );
}
