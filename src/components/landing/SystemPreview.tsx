import { MissionConsole } from "@/components/landing/MissionConsole";
import { ToolTile, type ToolTileData } from "@/components/landing/ToolTile";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusPill } from "@/components/ui/StatusPill";

const autonomyStages = [
  {
    name: "Strategy",
    body: "Convert founder intent into a clear wedge, operating constraints, budget, and target customer.",
    state: "Complete",
  },
  {
    name: "Research",
    body: "Turn market evidence into a decision record: segments, competitors, risks, and buyer budgets.",
    state: "Running",
  },
  {
    name: "Validation",
    body: "Generate customer tests, interview plans, and learning goals before the product hardens.",
    state: "Waiting",
  },
  {
    name: "Build",
    body: "Create scoped GitHub tasks and acceptance criteria for the smallest shippable preview.",
    state: "Waiting",
  },
  {
    name: "Deploy",
    body: "Prepare Vercel previews, deployment status, rollback notes, and approval gates.",
    state: "Blocked",
  },
  {
    name: "Learn",
    body: "Fold validation outcomes back into the next action instead of leaving the plan static.",
    state: "Complete",
  },
];

const checkpoints = [
  {
    title: "Approval before side effects",
    body: "Outbound messaging, public deploys, billing changes, and production writes stop at a human checkpoint.",
    state: "Waiting",
  },
  {
    title: "Risk flags stay visible",
    body: "Payment language, customer data, media rights, and tool access are labeled before agents continue.",
    state: "Running",
  },
  {
    title: "Rollback path included",
    body: "Every deploy step carries a rollback note, owner, and safe fallback before preview promotion.",
    state: "Complete",
  },
];

const tools: ToolTileData[] = [
  {
    name: "GitHub",
    role: "Issues, repo scaffolds, acceptance criteria, and implementation handoff.",
    access: "Approval gated",
    signal: "preview task prepared",
  },
  {
    name: "Vercel",
    role: "Preview deployment state, build readiness, and release checkpoint.",
    access: "Preview",
    signal: "deployment ready",
  },
  {
    name: "Supabase",
    role: "Saved businesses, auth state, execution records, and dashboard persistence.",
    access: "Read only",
    signal: "session-aware",
  },
  {
    name: "OpenAI",
    role: "Blueprint generation, agent reasoning, and validation prompt synthesis.",
    access: "Connected",
    signal: "route configured",
  },
  {
    name: "Stripe",
    role: "Billing placeholder for future launch experiments and paid pilot tracking.",
    access: "Preview",
    signal: "not connected",
  },
  {
    name: "Analytics",
    role: "Learning loop placeholder for activation, conversion, and validation outcomes.",
    access: "Preview",
    signal: "planned",
  },
];

function variantForState(state: string) {
  if (state === "Complete") return "success" as const;
  if (state === "Blocked") return "danger" as const;
  if (state === "Waiting") return "warning" as const;
  return "accent" as const;
}

export function SystemPreview() {
  return (
    <section className="relative overflow-hidden border-y border-border-subtle bg-surface/45 px-6 py-20 sm:py-28">
      <div aria-hidden className="grid-backdrop pointer-events-none absolute inset-0 opacity-40" />
      <div className="relative mx-auto max-w-6xl space-y-24">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,0.95fr)_minmax(24rem,1.05fr)]">
          <div>
            <Reveal>
              <SectionHeader
                eyebrow="Autonomy Layer"
                title="Execution flows through controlled stages"
                description="bucks.ai is an operating loop: each stage creates state for the next one, while the console keeps permission and risk visible."
              />
            </Reveal>

            <div className="mt-10 space-y-3">
              {autonomyStages.map((stage, index) => (
                <Reveal key={stage.name} delay={index * 70}>
                  <GlassPanel interactive className="p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
                          {String(index + 1).padStart(2, "0")}
                        </p>
                        <h3 className="mt-2 text-lg font-semibold text-foreground">
                          {stage.name}
                        </h3>
                        <p className="mt-2 text-sm leading-6 text-secondary">
                          {stage.body}
                        </p>
                      </div>
                      <StatusPill label={stage.state} variant={variantForState(stage.state)} />
                    </div>
                  </GlassPanel>
                </Reveal>
              ))}
            </div>
          </div>

          <div className="lg:sticky lg:top-28 lg:self-start">
            <MissionConsole compact />
          </div>
        </div>

        <div>
          <Reveal>
            <SectionHeader
              eyebrow="Human Checkpoints"
              title="Autonomy with brakes, approvals, and rollback paths"
              description="The system is built to execute, but not blindly. Risky actions surface as operator decisions before they touch customers or production."
            />
          </Reveal>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {checkpoints.map((checkpoint, index) => (
              <Reveal key={checkpoint.title} delay={index * 80}>
                <GlassPanel className="h-full p-5">
                  <StatusPill
                    label={checkpoint.state}
                    variant={variantForState(checkpoint.state)}
                  />
                  <h3 className="mt-4 text-lg font-semibold text-foreground">
                    {checkpoint.title}
                  </h3>
                  <p className="mt-3 text-sm leading-6 text-secondary">
                    {checkpoint.body}
                  </p>
                </GlassPanel>
              </Reveal>
            ))}
          </div>
        </div>

        <div>
          <Reveal>
            <SectionHeader
              eyebrow="Tool Mesh"
              title="Connected tools behave like controlled infrastructure"
              description="bucks.ai coordinates the tools a software business actually uses, with access mode and current signal visible on every tile."
            />
          </Reveal>
          <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {tools.map((tool, index) => (
              <Reveal key={tool.name} delay={index * 55}>
                <ToolTile tool={tool} />
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
