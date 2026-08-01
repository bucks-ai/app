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
    <section id="execution-flow" className="px-6 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <SectionHeader
            eyebrow="Mission Console"
            title="A startup idea becomes an execution pipeline"
            description="The interface is not a chat thread. It is a control plane: agents advance the work, tools stay permissioned, and human checkpoints interrupt risky moves."
          />
        </Reveal>

        <div className="mt-14 grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(22rem,0.85fr)]">
          <GlassPanel as="section" className="p-5 sm:p-6">
            <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
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

          <GlassPanel as="section" className="p-5 sm:p-6">
            <div className="mb-4 rounded-xl border border-status-pending/30 bg-status-pending/10 p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-status-pending">
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

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {proofMetrics.map(([value, label], index) => (
            <Reveal key={label} delay={index * 70}>
              <div className="neumorphic-soft rounded-card p-5">
                <p className="font-mono text-2xl font-semibold text-foreground">
                  {value}
                </p>
                <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  {label}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
