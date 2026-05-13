import type { Metadata } from "next";
import Link from "next/link";
import { BusinessDetail } from "@/components/dashboard/BusinessDetail";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { demoBusinesses, getDemoBusiness } from "@/components/dashboard/mock-data";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

export function generateStaticParams() {
  return demoBusinesses.map((business) => ({ id: business.id }));
}

export async function generateMetadata({
  params,
}: PageProps<"/dashboard/businesses/[id]">): Promise<Metadata> {
  const { id } = await params;
  const business = getDemoBusiness(id);

  return {
    title: business ? `${business.name} | bucks.ai` : "Business not found | bucks.ai",
    description: business
      ? `Demo business detail shell for ${business.name}.`
      : "Unknown demo business record.",
  };
}

export default async function BusinessDetailPage({
  params,
}: PageProps<"/dashboard/businesses/[id]">) {
  const { id } = await params;
  const business = getDemoBusiness(id);

  if (!business) {
    return (
      <DashboardShell>
        <div className="mx-auto max-w-3xl">
          <Link
            href="/dashboard"
            className="inline-flex text-sm font-medium text-[#A5B4FC] transition-colors hover:text-[#C7D2FE]"
          >
            &lt;- Back to Mission Control
          </Link>
          <OperatorPanel className="mt-8 p-6 text-center shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
            <div className="flex justify-center">
              <StatusPill label="No sample record" variant="neutral" />
            </div>
            <SectionLabel className="mt-6">Unknown business</SectionLabel>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[#F0F0F0]">
              This demo business does not exist.
            </h1>
            <p className="mt-4 text-sm leading-7 text-[#888888]">
              The dashboard currently reads from a local mock dataset only. Once
              Supabase is wired, this page can resolve real saved businesses.
            </p>
          </OperatorPanel>
        </div>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <BusinessDetail business={business} />
    </DashboardShell>
  );
}
