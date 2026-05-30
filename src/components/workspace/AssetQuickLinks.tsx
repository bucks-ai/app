import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus, ExecutionAsset } from "@/types/execution-ui";

type AssetQuickLinksProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  onBlueprintOpen?: () => void;
  compact?: boolean;
};

type QuickAsset = {
  id: string;
  label: string;
  value: string;
  href?: string | null;
  onClick?: () => void;
};

function findAsset(
  assets: ExecutionAsset[],
  type: ExecutionAsset["type"]
): ExecutionAsset | null {
  return assets.find((asset) => asset.type === type) ?? null;
}

export function AssetQuickLinks({
  business,
  executionStatus,
  compact = false,
}: AssetQuickLinksProps) {
  const assets = executionStatus?.assets ?? [];
  const githubAsset = findAsset(assets, "github_repo");
  const vercelAsset = findAsset(assets, "vercel_project");
  const deploymentAsset = findAsset(assets, "deployment_url");

  const quickAssets: QuickAsset[] = [
    {
      id: "deployment",
      label: "Live App URL",
      value: business.vercelProject?.deploymentUrl
        ? business.vercelProject.deploymentUrl
        : deploymentAsset?.label ??
          (business.vercelProject || vercelAsset ? "Deployment pending" : "Pending"),
      href: business.vercelProject?.deploymentUrl ?? deploymentAsset?.url,
    },
    {
      id: "vercel",
      label: "Vercel Project",
      value: business.vercelProject?.projectName ?? vercelAsset?.label ?? "Pending",
      href: business.vercelProject?.dashboardUrl ?? vercelAsset?.url,
    },
    {
      id: "github",
      label: "GitHub Repo",
      value: business.githubRepo?.fullName ?? githubAsset?.label ?? "Pending",
      href: business.githubRepo?.repoUrl ?? githubAsset?.url,
    },
  ];

  return (
    <div className={compact ? "space-y-1.5" : "grid gap-2 sm:grid-cols-2 xl:grid-cols-5"}>
      {quickAssets.map((asset) => {
        const available = Boolean(asset.href || asset.onClick);
        const className = compact
          ? `flex w-full items-center justify-between gap-2 rounded border px-2.5 py-2 text-left transition-colors ${
              available
                ? "border-[#1C1C1C] bg-[#080808] hover:border-[#4F46E5]/45"
                : "border-[#1C1C1C] bg-[#080808] opacity-55"
            }`
          : `flex min-w-0 flex-col rounded border px-3 py-2.5 transition-colors ${
              available
                ? "border-[#1C1C1C] bg-[#080808] hover:border-[#4F46E5]/45"
                : "border-[#1C1C1C] bg-[#080808] opacity-55"
            }`;

        const content = (
          <>
            <span className="font-mono text-[10px] uppercase tracking-widest text-[#555]">
              {asset.label}
            </span>
            <span
              className={`min-w-0 truncate text-xs ${
                available ? "text-[#D4D4D4]" : "text-[#555]"
              }`}
            >
              {asset.value}
            </span>
          </>
        );

        if (asset.href) {
          return (
            <a
              key={asset.id}
              href={asset.href}
              target={asset.href.startsWith("http") ? "_blank" : undefined}
              rel={asset.href.startsWith("http") ? "noopener noreferrer" : undefined}
              className={className}
            >
              {content}
            </a>
          );
        }

        if (asset.onClick) {
          return (
            <button key={asset.id} type="button" onClick={asset.onClick} className={className}>
              {content}
            </button>
          );
        }

        return (
          <div key={asset.id} className={className}>
            {content}
          </div>
        );
      })}
    </div>
  );
}
