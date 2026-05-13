import type { Metadata } from "next";
import Link from "next/link";
import { ActivityLog } from "@/components/dashboard/ActivityLog";
import { BusinessCard } from "@/components/dashboard/BusinessCard";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { HumanActionQueue } from "@/components/dashboard/HumanActionQueue";
import { ToolPermissionSummary } from "@/components/dashboard/ToolPermissionSummary";
import {
  demoActivity,
  demoBusinesses,
  demoHumanActions,
  demoPermissions,
} from "@/components/dashboard/mock-data";
import { DataTile } from "@/components/ui/DataTile";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

export const metadata: Metadata = {
  title: "Mission Control | bucks.ai",
  description:
    "A mock dashboard shell for saved startup builds, operator runs, human-required actions, and tool permissions.",
};

export default function DashboardPage() {
  return (
    <DashboardShell>
      <div className="space-y-8">
        <OperatorPanel className="overflow-hidden p-6 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
          <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-4xl">
              <div className="flex flex-wrap items-center gap-3">
                <SectionLabel>Mission Control</SectionLabel>
                <StatusPill label="Demo data" variant="neutral" />
              </div>
              <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
                Saved startup builds and operator runs
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-8 text-[#888888] sm:text-lg">
                This is the frontend shell where authenticated founders will
                return to monitor businesses, agent activity, approvals, and
                tool permissions. All records shown here are sample data.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row lg:flex-col xl:flex-row">
              <Link
                href="/intake"
                className="rounded-md bg-[#4F46E5] px-4 py-3 text-center text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1]"
              >
                New blueprint -&gt;
              </Link>
              <Link
                href="/tools"
                className="rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 text-center text-sm font-semibold text-[#D4D4D4] transition-colors hover:border-[#4F46E5]/60 hover:text-[#F0F0F0]"
              >
                Tool registry -&gt;
              </Link>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <DataTile
              label="Sample businesses"
              value={`${demoBusinesses.length}`}
              detail="Mock saved builds for the auth dashboard shell."
              tone="accent"
            />
            <DataTile
              label="Human queue"
              value={`${demoHumanActions.length}`}
              detail="Approval-gated examples only; no live actions are queued."
              tone="warning"
            />
            <DataTile
              label="Auth state"
              value="Not wired"
              detail="Supabase sessions are intentionally deferred."
            />
            <DataTile
              label="Data source"
              value="Demo"
              detail="No database reads or writes happen on this branch."
              tone="neutral"
            />
          </div>
        </OperatorPanel>

        <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <OperatorPanel className="p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <SectionLabel>Saved businesses</SectionLabel>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[#F0F0F0]">
                  Sample build records
                </h2>
              </div>
              <p className="max-w-md text-sm leading-6 text-[#888888]">
                Demo/sample data only. These do not represent real user projects.
              </p>
            </div>
            <div className="mt-6 grid gap-4">
              {demoBusinesses.map((business) => (
                <BusinessCard key={business.id} business={business} />
              ))}
            </div>
          </OperatorPanel>

          <div className="grid gap-6">
            <OperatorPanel className="p-6">
              <SectionLabel>Recent agent activity</SectionLabel>
              <div className="mt-5">
                <ActivityLog items={demoActivity} />
              </div>
            </OperatorPanel>

            <OperatorPanel className="p-6" elevated>
              <SectionLabel tone="warning">Human-required action queue</SectionLabel>
              <div className="mt-5">
                <HumanActionQueue actions={demoHumanActions} />
              </div>
            </OperatorPanel>
          </div>
        </section>

        <OperatorPanel className="p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <SectionLabel>Tool permissions summary</SectionLabel>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[#F0F0F0]">
                Mock operating permissions
              </h2>
            </div>
            <StatusPill label="No live integrations" variant="neutral" />
          </div>
          <ToolPermissionSummary
            permissions={demoPermissions}
            className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4"
          />
        </OperatorPanel>
      </div>
    </DashboardShell>
  );
}
