import Link from "next/link";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";

type BusinessCardProps = {
  business: DashboardBusiness;
};

export function BusinessCard({ business }: BusinessCardProps) {
  return (
    <Link
      href={`/dashboard/businesses/${business.id}`}
      className="group block rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-5 transition-colors hover:border-[#4F46E5]/60 hover:bg-[#141414]"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <SectionLabel tone="muted">Sample business</SectionLabel>
          <h3 className="mt-3 text-xl font-semibold tracking-tight text-[#F0F0F0]">
            {business.name}
          </h3>
          <p className="mt-2 font-mono text-xs uppercase tracking-[0.18em] text-[#888888]">
            {business.businessType}
          </p>
        </div>
        <StatusPill label={business.status} variant={business.statusVariant} />
      </div>
      <dl className="mt-6 grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-md border border-[#1C1C1C] bg-[#080808] p-3">
          <dt className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
            Goal
          </dt>
          <dd className="mt-2 leading-6 text-[#D4D4D4]">{business.goal}</dd>
        </div>
        <div className="rounded-md border border-[#1C1C1C] bg-[#080808] p-3">
          <dt className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
            Created
          </dt>
          <dd className="mt-2 leading-6 text-[#D4D4D4]">{business.created}</dd>
        </div>
      </dl>
      <p className="mt-5 text-sm font-medium text-[#A5B4FC] transition-colors group-hover:text-[#C7D2FE]">
        Open build record -&gt;
      </p>
    </Link>
  );
}
