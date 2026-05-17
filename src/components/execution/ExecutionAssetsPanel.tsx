import Link from "next/link";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { ExecutionStatusPill } from "@/components/execution/ExecutionStatusPill";
import type { ExecutionAsset } from "@/types/execution-ui";

type ExecutionAssetsPanelProps = {
  assets: ExecutionAsset[];
};

function assetTypeLabel(type: ExecutionAsset["type"]) {
  if (type === "github_repo") return "GitHub repo";
  if (type === "vercel_project") return "Vercel project";
  if (type === "deployment_url") return "Deployment URL";
  if (type === "tool_permissions") return "Tool permissions";
  return type.charAt(0).toUpperCase() + type.slice(1);
}

export function ExecutionAssetsPanel({ assets }: ExecutionAssetsPanelProps) {
  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-5">
      <SectionLabel>External assets</SectionLabel>
      <div className="mt-4 space-y-3">
        {assets.length > 0 ? (
          assets.map((asset) => (
            <div key={asset.id} className="rounded-md border border-[#1C1C1C] bg-[#0F0F0F] p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                    {assetTypeLabel(asset.type)}
                  </p>
                  <h3 className="mt-2 break-words text-sm font-semibold text-[#F0F0F0]">
                    {asset.label}
                  </h3>
                </div>
                {asset.status ? <ExecutionStatusPill label={asset.status} /> : null}
              </div>
              {asset.description ? (
                <p className="mt-3 text-sm leading-6 text-[#888888]">{asset.description}</p>
              ) : null}
              {asset.url ? (
                <Link
                  href={asset.url}
                  target={asset.url.startsWith("http") ? "_blank" : undefined}
                  rel={asset.url.startsWith("http") ? "noreferrer" : undefined}
                  className="mt-4 inline-flex max-w-full rounded-md border border-[#4F46E5]/35 px-3 py-2 text-sm font-semibold text-[#A5B4FC] transition-colors hover:border-[#818CF8]/70 hover:text-[#C7D2FE]"
                >
                  <span className="truncate">Open asset</span>
                </Link>
              ) : null}
            </div>
          ))
        ) : (
          <p className="rounded-md border border-[#1C1C1C] bg-[#0F0F0F] p-4 text-sm leading-6 text-[#888888]">
            No external assets are recorded yet.
          </p>
        )}
      </div>
    </div>
  );
}
