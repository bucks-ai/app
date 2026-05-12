"use client";

import type { BusinessBlueprint, StartupIdea } from "@/types/startup";
import { BlueprintSection } from "@/components/intake/BlueprintSection";

type BlueprintPreviewProps = {
  idea: StartupIdea;
  blueprint: BusinessBlueprint;
  onEditIdea: () => void;
};

function Pill({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-white/10 bg-white/[0.06] px-3 py-1 text-xs font-medium text-neutral-200">
      {label}
    </span>
  );
}

function TextList({ items }: { items: string[] }) {
  return (
    <div className="grid gap-3">
      {items.map((item) => (
        <div
          key={item}
          className="rounded-2xl border border-white/8 bg-black/25 px-4 py-3 text-sm leading-6 text-neutral-300"
        >
          {item}
        </div>
      ))}
    </div>
  );
}

export function BlueprintPreview({
  idea,
  blueprint,
  onEditIdea,
}: BlueprintPreviewProps) {
  return (
    <div className="space-y-6">
      <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.22),_transparent_35%),linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] p-8 shadow-[0_30px_120px_rgba(0,0,0,0.45)]">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="inline-flex rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.28em] text-emerald-300">
              Blueprint Ready
            </div>
            <h1 className="mt-5 text-4xl font-semibold tracking-tight text-white sm:text-5xl">
              {idea.ideaName || "Untitled startup"} Mission Control
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-neutral-300 sm:text-lg">
              {blueprint.businessSummary}
            </p>
          </div>

          <div className="flex flex-col items-start gap-3 lg:items-end">
            <button
              type="button"
              onClick={onEditIdea}
              className="rounded-full border border-white/15 bg-white/5 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:border-white/30 hover:bg-white/10"
            >
              Edit Idea
            </button>
            <div className="flex flex-wrap gap-2 lg:justify-end">
              <Pill label={blueprint.businessType} />
              <Pill label={idea.autonomyPreference} />
              <Pill label={`Budget: ${idea.budget || "TBD"}`} />
              <Pill label={`Timeline: ${idea.timeline || "TBD"}`} />
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6">
          <BlueprintSection
            title="Business Summary"
            description="The initial business framing based on the founder intake."
          >
            <p className="text-sm leading-7 text-neutral-300">
              {blueprint.businessSummary}
            </p>
          </BlueprintSection>

          <div className="grid gap-6 lg:grid-cols-2">
            <BlueprintSection title="Startup Classification">
              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/8 p-4">
                <p className="text-sm font-medium text-emerald-300">
                  {blueprint.businessType}
                </p>
              </div>
            </BlueprintSection>

            <BlueprintSection title="Target Customer">
              <p className="text-sm leading-7 text-neutral-300">
                {blueprint.targetCustomer}
              </p>
            </BlueprintSection>
          </div>

          <BlueprintSection title="Pain Hypothesis">
            <p className="text-sm leading-7 text-neutral-300">
              {blueprint.painHypothesis}
            </p>
          </BlueprintSection>

          <BlueprintSection title="MVP Scope">
            <TextList items={blueprint.mvpScope} />
          </BlueprintSection>

          <BlueprintSection title="Differentiation">
            <TextList items={blueprint.differentiation} />
          </BlueprintSection>

          <BlueprintSection title="Suggested Stack">
            <TextList items={blueprint.suggestedStack} />
          </BlueprintSection>

          <BlueprintSection title="Required Tools">
            <div className="grid gap-3 md:grid-cols-2">
              {blueprint.requiredTools.map((tool) => (
                <div
                  key={`${tool.name}-${tool.category}`}
                  className="rounded-2xl border border-white/8 bg-black/25 p-4"
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-white">
                      {tool.name}
                    </h3>
                    <span className="rounded-full border border-white/10 bg-white/6 px-2.5 py-1 text-[11px] uppercase tracking-[0.22em] text-neutral-400">
                      {tool.category}
                    </span>
                  </div>
                  <p className="text-sm leading-6 text-neutral-400">
                    {tool.purpose}
                  </p>
                </div>
              ))}
            </div>
          </BlueprintSection>

          <BlueprintSection title="Required Permissions">
            <div className="grid gap-3">
              {blueprint.requiredPermissions.map((permission) => (
                <div
                  key={permission.title}
                  className="rounded-2xl border border-white/8 bg-black/25 p-4"
                >
                  <div className="mb-2 flex flex-wrap items-center gap-3">
                    <h3 className="text-sm font-semibold text-white">
                      {permission.title}
                    </h3>
                    <span className="rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-[11px] uppercase tracking-[0.22em] text-amber-300">
                      {permission.level}
                    </span>
                  </div>
                  <p className="text-sm leading-6 text-neutral-400">
                    {permission.reason}
                  </p>
                </div>
              ))}
            </div>
          </BlueprintSection>

          <BlueprintSection title="Go-To-Market Motion">
            <p className="text-sm leading-7 text-neutral-300">
              {blueprint.goToMarketMotion}
            </p>
          </BlueprintSection>
        </div>

        <div className="space-y-6">
          <BlueprintSection title="Marketing Plan">
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-white">Channels</h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  {blueprint.marketingPlan.channels.map((channel) => (
                    <Pill key={channel} label={channel} />
                  ))}
                </div>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Launch Assets</h3>
                <TextList items={blueprint.marketingPlan.launchAssets} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Experiments</h3>
                <TextList items={blueprint.marketingPlan.experiments} />
              </div>
            </div>
          </BlueprintSection>

          <BlueprintSection title="Sales / Outreach Plan">
            <div className="space-y-4">
              <p className="text-sm leading-7 text-neutral-300">
                {blueprint.salesPlan.motion}
              </p>
              <div>
                <h3 className="text-sm font-semibold text-white">Channels</h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  {blueprint.salesPlan.channels.map((channel) => (
                    <Pill key={channel} label={channel} />
                  ))}
                </div>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">
                  Enablement
                </h3>
                <TextList items={blueprint.salesPlan.enablement} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">
                  Sequence
                </h3>
                <TextList items={blueprint.salesPlan.sequence} />
              </div>
            </div>
          </BlueprintSection>

          <BlueprintSection title="Analytics Plan">
            <div className="space-y-4">
              <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/8 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">
                  North Star
                </p>
                <p className="mt-2 text-sm text-white">
                  {blueprint.analyticsPlan.northStarMetric}
                </p>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Events</h3>
                <TextList items={blueprint.analyticsPlan.events} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Dashboards</h3>
                <TextList items={blueprint.analyticsPlan.dashboards} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">
                  Review Cadence
                </h3>
                <TextList items={blueprint.analyticsPlan.reviewCadence} />
              </div>
            </div>
          </BlueprintSection>

          <BlueprintSection title="Human-Required Actions">
            <div className="grid gap-3">
              {blueprint.humanRequiredActions.map((action) => (
                <div
                  key={action.title}
                  className="rounded-2xl border border-amber-500/15 bg-amber-500/6 p-4"
                >
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="text-sm font-semibold text-white">
                      {action.title}
                    </h3>
                    <span className="rounded-full border border-white/10 bg-white/6 px-2.5 py-1 text-[11px] uppercase tracking-[0.22em] text-neutral-400">
                      {action.owner}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-neutral-400">
                    {action.reason}
                  </p>
                </div>
              ))}
            </div>
          </BlueprintSection>

          <BlueprintSection title="Next Autonomous Actions">
            <div className="grid gap-3">
              {blueprint.nextAutonomousActions.map((action) => (
                <div
                  key={action.title}
                  className="rounded-2xl border border-white/8 bg-black/25 p-4"
                >
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-white">
                      {action.title}
                    </h3>
                    <span className="rounded-full border border-emerald-500/15 bg-emerald-500/8 px-2.5 py-1 text-[11px] uppercase tracking-[0.22em] text-emerald-300">
                      {action.phase}
                    </span>
                  </div>
                  <p className="text-sm leading-6 text-neutral-400">
                    {action.detail}
                  </p>
                </div>
              ))}
            </div>
          </BlueprintSection>

          <BlueprintSection title="Risks">
            <TextList items={blueprint.risks} />
          </BlueprintSection>

          <BlueprintSection title="Success Metrics">
            <TextList items={blueprint.successMetrics} />
          </BlueprintSection>

          <BlueprintSection title="Kill Criteria">
            <TextList items={blueprint.killCriteria} />
          </BlueprintSection>
        </div>
      </div>
    </div>
  );
}
