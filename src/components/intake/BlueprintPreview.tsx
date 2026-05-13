"use client";

import Link from "next/link";
import type { BusinessBlueprint, StartupIdea } from "@/types/startup";
import { BlueprintSection } from "@/components/intake/BlueprintSection";
import { DataTile } from "@/components/ui/DataTile";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

type BlueprintPreviewProps = {
  idea: StartupIdea;
  blueprint: BusinessBlueprint;
  onEditIdea: () => void;
  savedBusinessId?: string;
  saveStatus?: "idle" | "checking" | "saving" | "saved" | "unauthenticated" | "error";
  saveError?: string;
};

function TextList({
  items,
  tone = "neutral",
}: {
  items: string[];
  tone?: "neutral" | "warning" | "danger" | "accent";
}) {
  const toneClasses = {
    neutral: "border-[#1C1C1C] bg-[#080808] text-[#D4D4D4]",
    warning: "border-[#F59E0B]/25 bg-[#F59E0B]/10 text-[#FDE68A]",
    danger: "border-[#EF4444]/30 bg-[#EF4444]/10 text-[#FECACA]",
    accent: "border-[#4F46E5]/30 bg-[#4F46E5]/10 text-[#C7D2FE]",
  };

  return (
    <div className="grid gap-3">
      {items.map((item) => (
        <div
          key={item}
          className={`rounded-md border px-4 py-3 text-sm leading-6 ${toneClasses[tone]}`}
        >
          {item}
        </div>
      ))}
    </div>
  );
}

function QueueItem({
  label,
  title,
  detail,
  tone = "accent",
}: {
  label: string;
  title: string;
  detail: string;
  tone?: "accent" | "warning";
}) {
  return (
    <div className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-[#F0F0F0]">{title}</h3>
        <StatusPill
          label={label}
          variant={tone === "warning" ? "warning" : "accent"}
        />
      </div>
      <p className="text-sm leading-6 text-[#888888]">{detail}</p>
    </div>
  );
}

export function BlueprintPreview({
  idea,
  blueprint,
  onEditIdea,
  savedBusinessId,
  saveStatus = "idle",
  saveError,
}: BlueprintPreviewProps) {
  return (
    <div className="space-y-6">
      <OperatorPanel className="overflow-hidden p-6 shadow-[0_30px_120px_rgba(0,0,0,0.45)] sm:p-8">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <SectionLabel>Blueprint Ready</SectionLabel>
            <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
              {idea.ideaName || "Untitled startup"} Mission Control
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[#888888] sm:text-lg">
              {blueprint.businessSummary}
            </p>
          </div>

          <div className="flex flex-col items-start gap-3 lg:items-end">
            <button
              type="button"
              onClick={onEditIdea}
              className="rounded-md border border-[#1C1C1C] bg-[#141414] px-5 py-2.5 text-sm font-medium text-[#F0F0F0] transition-colors hover:border-[#2A2A2A] hover:bg-[#191919]"
            >
              Edit Idea
            </button>
            <div className="flex flex-wrap gap-2 lg:justify-end">
              <StatusPill label="Stack selected" variant="accent" />
              <StatusPill label="GTM mapped" variant="accent" />
              <StatusPill label="Permissions pending" variant="warning" />
              <StatusPill label="Human gates identified" variant="warning" />
            </div>
          </div>
        </div>

        {saveStatus !== "idle" ? (
          <div
            className={`mt-8 rounded-lg border p-4 ${
              saveStatus === "saved"
                ? "border-[#22C55E]/25 bg-[#22C55E]/10"
                : saveStatus === "error"
                  ? "border-[#F59E0B]/35 bg-[#F59E0B]/10"
                  : saveStatus === "unauthenticated"
                    ? "border-[#4F46E5]/35 bg-[#4F46E5]/10"
                    : "border-[#1C1C1C] bg-[#080808]"
            }`}
          >
            {saveStatus === "saved" && savedBusinessId ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <StatusPill label="Saved to Mission Control" variant="success" />
                  <p className="mt-3 text-sm leading-6 text-[#D4D4D4]">
                    This blueprint is now attached to a saved business project.
                  </p>
                </div>
                <Link
                  href={`/dashboard/businesses/${savedBusinessId}`}
                  className="rounded-md bg-[#4F46E5] px-4 py-2.5 text-center text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1]"
                >
                  Open in dashboard -&gt;
                </Link>
              </div>
            ) : null}

            {saveStatus === "unauthenticated" ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <StatusPill label="Not saved" variant="accent" />
                  <p className="mt-3 text-sm leading-6 text-[#C7D2FE]">
                    Create an account to save this build.
                  </p>
                </div>
                <Link
                  href="/signup"
                  className="rounded-md border border-[#4F46E5]/45 bg-[#4F46E5]/10 px-4 py-2.5 text-center text-sm font-semibold text-[#C7D2FE] transition-colors hover:bg-[#4F46E5]/15"
                >
                  Create account -&gt;
                </Link>
              </div>
            ) : null}

            {saveStatus === "checking" || saveStatus === "saving" ? (
              <div className="flex items-center gap-3">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#A5B4FC] border-t-transparent" />
                <p className="text-sm font-medium text-[#A5B4FC]">
                  {saveStatus === "checking"
                    ? "Checking Mission Control session..."
                    : "Saving blueprint to Mission Control..."}
                </p>
              </div>
            ) : null}

            {saveStatus === "error" ? (
              <div>
                <StatusPill label="Save warning" variant="warning" />
                <p className="mt-3 text-sm leading-6 text-[#FDE68A]">
                  {saveError ?? "Blueprint generated, but saving failed."}
                </p>
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="mt-8 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <DataTile
            label="Startup"
            value={idea.ideaName || "Untitled"}
            detail={blueprint.businessType}
            className="xl:col-span-1"
          />
          <DataTile
            label="Customer"
            value={blueprint.targetCustomer || "TBD"}
            detail="First wedge"
            className="xl:col-span-2"
          />
          <DataTile
            label="Goal"
            value={idea.primaryGoal || "TBD"}
            detail={idea.successMetric || "Success metric pending"}
            className="xl:col-span-2"
          />
          <DataTile
            label="Autonomy"
            value={idea.autonomyPreference}
            detail={idea.spendingLimit || "No spend threshold supplied"}
            tone="accent"
            className="xl:col-span-2"
          />
          <DataTile
            label="Runway"
            value={idea.budget || "TBD"}
            detail={idea.timeline || "Timeline pending"}
            className="xl:col-span-3"
          />
        </div>
      </OperatorPanel>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6">
          <BlueprintSection
            title="Business / Product"
            description="Initial operating frame for product scope, customer pain, and build direction."
          >
            <div className="space-y-5">
              <div>
                <SectionLabel tone="muted">Summary</SectionLabel>
                <p className="mt-2 text-sm leading-7 text-[#D4D4D4]">
                  {blueprint.businessSummary}
                </p>
              </div>
              <div>
                <SectionLabel tone="muted">Pain hypothesis</SectionLabel>
                <p className="mt-2 text-sm leading-7 text-[#D4D4D4]">
                  {blueprint.painHypothesis}
                </p>
              </div>
              <div>
                <SectionLabel tone="muted">MVP scope</SectionLabel>
                <div className="mt-3">
                  <TextList items={blueprint.mvpScope} />
                </div>
              </div>
              <div>
                <SectionLabel tone="muted">Differentiation</SectionLabel>
                <div className="mt-3">
                  <TextList items={blueprint.differentiation} />
                </div>
              </div>
            </div>
          </BlueprintSection>

          <BlueprintSection title="Suggested Stack">
            <TextList items={blueprint.suggestedStack} tone="accent" />
          </BlueprintSection>

          <BlueprintSection title="Required Tools">
            <div className="grid gap-3">
              {blueprint.requiredTools.map((tool) => (
                <div
                  key={`${tool.name}-${tool.category}`}
                  className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4"
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-[#F0F0F0]">
                      {tool.name}
                    </h3>
                    <StatusPill label={tool.category} />
                  </div>
                  <p className="text-sm leading-6 text-[#888888]">
                    {tool.purpose}
                  </p>
                </div>
              ))}
            </div>
          </BlueprintSection>
        </div>

        <div className="space-y-6">
          <BlueprintSection
            title="GTM / Marketing / Sales"
            description="Launch motion, channel choices, experiments, and first sales operating queue."
          >
            <div className="space-y-5">
              <div>
                <SectionLabel tone="muted">GTM motion</SectionLabel>
                <p className="mt-2 text-sm leading-7 text-[#D4D4D4]">
                  {blueprint.goToMarketMotion}
                </p>
              </div>
              <div>
                <SectionLabel tone="muted">Marketing channels</SectionLabel>
                <div className="mt-3 flex flex-wrap gap-2">
                  {blueprint.marketingPlan.channels.map((channel) => (
                    <StatusPill key={channel} label={channel} variant="accent" />
                  ))}
                </div>
              </div>
              <div>
                <SectionLabel tone="muted">Launch assets</SectionLabel>
                <div className="mt-3">
                  <TextList items={blueprint.marketingPlan.launchAssets} />
                </div>
              </div>
              <div>
                <SectionLabel tone="muted">Experiments</SectionLabel>
                <div className="mt-3">
                  <TextList items={blueprint.marketingPlan.experiments} />
                </div>
              </div>
            </div>
          </BlueprintSection>

          <BlueprintSection title="Sales / Outreach Plan">
            <div className="space-y-5">
              <p className="text-sm leading-7 text-[#D4D4D4]">
                {blueprint.salesPlan.motion}
              </p>
              <div>
                <SectionLabel tone="muted">Channels</SectionLabel>
                <div className="mt-3 flex flex-wrap gap-2">
                  {blueprint.salesPlan.channels.map((channel) => (
                    <StatusPill key={channel} label={channel} />
                  ))}
                </div>
              </div>
              <div>
                <SectionLabel tone="muted">Enablement</SectionLabel>
                <div className="mt-3">
                  <TextList items={blueprint.salesPlan.enablement} />
                </div>
              </div>
              <div>
                <SectionLabel tone="muted">Sequence</SectionLabel>
                <div className="mt-3">
                  <TextList items={blueprint.salesPlan.sequence} />
                </div>
              </div>
            </div>
          </BlueprintSection>

          <BlueprintSection title="Analytics Plan">
            <div className="space-y-5">
              <DataTile
                label="North Star"
                value={blueprint.analyticsPlan.northStarMetric}
                tone="accent"
              />
              <div>
                <SectionLabel tone="muted">Events</SectionLabel>
                <div className="mt-3">
                  <TextList items={blueprint.analyticsPlan.events} />
                </div>
              </div>
              <div>
                <SectionLabel tone="muted">Dashboards</SectionLabel>
                <div className="mt-3">
                  <TextList items={blueprint.analyticsPlan.dashboards} />
                </div>
              </div>
              <div>
                <SectionLabel tone="muted">Review cadence</SectionLabel>
                <div className="mt-3">
                  <TextList items={blueprint.analyticsPlan.reviewCadence} />
                </div>
              </div>
            </div>
          </BlueprintSection>
        </div>

        <div className="space-y-6">
          <BlueprintSection
            title="Controls / Permissions"
            description="Human-required checkpoints and boundaries before autonomous execution."
          >
            <div className="space-y-4">
              {blueprint.requiredPermissions.map((permission) => (
                <QueueItem
                  key={permission.title}
                  label={permission.level}
                  title={permission.title}
                  detail={permission.reason}
                  tone="warning"
                />
              ))}
            </div>
          </BlueprintSection>

          <BlueprintSection title="Human-Required Actions">
            <div className="grid gap-3">
              {blueprint.humanRequiredActions.map((action) => (
                <QueueItem
                  key={action.title}
                  label={action.owner}
                  title={action.title}
                  detail={action.reason}
                  tone="warning"
                />
              ))}
            </div>
          </BlueprintSection>

          <BlueprintSection title="Next Autonomous Actions">
            <div className="grid gap-3">
              {blueprint.nextAutonomousActions.map((action) => (
                <QueueItem
                  key={action.title}
                  label={action.phase}
                  title={action.title}
                  detail={action.detail}
                />
              ))}
            </div>
          </BlueprintSection>

          <BlueprintSection title="Risks">
            <TextList items={blueprint.risks} tone="danger" />
          </BlueprintSection>

          <BlueprintSection title="Success Metrics">
            <div className="grid gap-3">
              {blueprint.successMetrics.map((metric, index) => (
                <DataTile
                  key={metric}
                  label={`Metric ${index + 1}`}
                  value={metric}
                  tone="success"
                />
              ))}
            </div>
          </BlueprintSection>

          <BlueprintSection title="Kill Criteria">
            <TextList items={blueprint.killCriteria} tone="warning" />
          </BlueprintSection>
        </div>
      </div>
    </div>
  );
}
