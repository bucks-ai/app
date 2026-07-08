import { ExecutionLog, type ExecutionLogItem } from "@/components/landing/ExecutionLog";
import { CTAButton } from "@/components/ui/CTAButton";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeader } from "@/components/ui/SectionHeader";

const proofLog: ExecutionLogItem[] = [
  { time: "14:02", actor: "validation", event: "Created validation plan for agency operations buyers.", tone: "success" },
  { time: "14:08", actor: "build", event: "Generated landing page variant for operator positioning.", tone: "accent" },
  { time: "14:12", actor: "github", event: "Prepared GitHub issue with scope, files, and acceptance criteria.", tone: "neutral" },
  { time: "14:17", actor: "vercel", event: "Preview deployment ready behind release approval.", tone: "success" },
  { time: "14:19", actor: "founder", event: "Awaiting approval for public preview and outbound script.", tone: "warning" },
];

export function ClosingCTA() {
  return (
    <section className="px-6 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(24rem,1.1fr)] lg:items-end">
          <Reveal>
            <SectionHeader
              eyebrow="Build Log"
              title="Proof that the system is doing work"
              description="The product should feel alive because it is tracking executable work: plans created, tasks prepared, previews gated, and approvals surfaced."
            />
          </Reveal>
          <Reveal delay={100}>
            <ExecutionLog items={proofLog} />
          </Reveal>
        </div>

        <Reveal>
          <GlassPanel
            className="mt-16 px-6 py-14 text-center sm:px-12"
            innerClassName="relative"
          >
            <p className="mx-auto max-w-xl font-mono text-[11px] uppercase tracking-[0.18em] text-accent-bright">
              Enter the operating console
            </p>
            <h2 className="text-balance mx-auto mt-4 max-w-3xl text-3xl font-semibold tracking-tight text-foreground sm:text-5xl">
              Put execution, tools, agents, and approvals in one loop.
            </h2>
            <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-secondary">
              Start with a software-business idea. bucks.ai turns it into a
              controlled operating system for strategy, build, deployment, and
              learning.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <CTAButton href="/dashboard" arrow className="w-full sm:w-auto">
                Enter the console
              </CTAButton>
              <CTAButton
                href="/intake"
                variant="secondary"
                className="w-full sm:w-auto"
              >
                Start a new run
              </CTAButton>
            </div>
          </GlassPanel>
        </Reveal>
      </div>
    </section>
  );
}
