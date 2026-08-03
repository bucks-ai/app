import { AnimatedProgressRail, type RailStage } from "@/components/landing/AnimatedProgressRail";
import { ExecutionLog, type ExecutionLogItem } from "@/components/landing/ExecutionLog";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusPill } from "@/components/ui/StatusPill";

const stages: RailStage[] = [
  {
    label: "Strategy Agent",
    detail: "Mapping business model, ICP, wedge, and launch constraints.",
    status: "Complete",
  },
  {
    label: "Research Agent",
    detail: "Analyzing market signals, competitors, budgets, and evidence.",
    status: "Running",
  },
  {
    label: "Validation Agent",
    detail: "Creating customer test plan and interview prompts.",
    status: "Waiting for approval",
  },
  {
    label: "Build Agent",
    detail: "Preparing GitHub task scope for a shippable preview.",
    status: "Waiting for approval",
  },
  {
    label: "Deploy Agent",
    detail: "Vercel preview ready behind founder checkpoint.",
    status: "Blocked",
  },
];

const executionEvents: ExecutionLogItem[] = [
  { time: "12:08", actor: "strategy", event: "Locked wedge: workflow ops for AI-native agencies.", tone: "accent" },
  { time: "12:11", actor: "research", event: "Clustered 31 market signals into 4 validation bets.", tone: "success" },
  { time: "12:16", actor: "validation", event: "Created customer test plan for 12 founder interviews.", tone: "accent" },
  { time: "12:19", actor: "build", event: "Prepared GitHub issue with acceptance criteria.", tone: "neutral" },
  { time: "12:21", actor: "deploy", event: "Preview deployment ready; awaiting founder approval.", tone: "warning" },
];

const proofMetrics = [
  ["1 brief", "becomes operating constraints"],
  ["5 lanes", "advance under permissions"],
  ["0 side effects", "without founder approval"],
];

export function WorkflowSteps() {
  return (
    <section id="execution-flow" className="relative px-6 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <SectionHeader
            eyebrow="Mission Console"
            title="A startup idea becomes an execution pipeline"
            description="The interface is not a chat thread. It is a control plane: agents advance the work, tools stay permissioned, and human checkpoints interrupt risky moves."
          />
        </Reveal>

        <div className="scroll-settle mt-16 grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(22rem,0.95fr)]">
          <GlassPanel as="section" className="p-6 sm:p-8">
            <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Current run
                </p>
                <h3 className="mt-2 text-xl font-semibold tracking-tight text-foreground">
                  ClipForge AI launch loop
                </h3>
              </div>
              <StatusPill label="Running" variant="accent" />
            </div>
            <AnimatedProgressRail stages={stages} />
          </GlassPanel>

          <GlassPanel as="section" className="p-6 sm:p-8">
            {/* Kept as a distinct surface — this one is a real semantic
                interruption, not decoration — but softened to a left rule
                and a tint rather than a full outlined box. */}
            <div className="mb-6 rounded-r-xl border-l-2 border-status-pending/50 bg-status-pending/[0.07] py-4 pl-5 pr-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-status-pending">
                Operator checkpoint
              </p>
              <p className="mt-2 text-sm font-semibold text-foreground">
                Founder approval required before preview goes public.
              </p>
              <p className="mt-2 text-sm leading-6 text-foreground-secondary">
                Vercel is prepared. Deployment remains gated until permissions
                and customer-facing copy are approved.
              </p>
            </div>
            <ExecutionLog items={executionEvents} />
          </GlassPanel>
        </div>

        {/* Three tiles became three statements. Same content, no containers —
            the hairline above the row is the only division needed. */}
        <div className="mt-12 grid gap-8 border-t border-edge pt-10 md:grid-cols-3">
          {proofMetrics.map(([value, label], index) => (
            <Reveal key={label} delay={index * 70}>
              <p className="font-mono text-2xl font-semibold text-foreground">
                {value}
              </p>
              <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                {label}
              </p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
