import Link from "next/link";
import { AnimatedPipeline, type PipelineStage } from "@/components/ui/AnimatedPipeline";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatusChip } from "@/components/ui/StatusChip";

const capabilities = ["Research", "Build", "Deploy", "Validate", "Agents"];

const stages: PipelineStage[] = [
  { label: "Research", detail: "Market + competitor scan", status: "done" },
  { label: "Blueprint", detail: "Strategy & MVP scope", status: "done" },
  { label: "Deploy", detail: "GitHub + Vercel starter", status: "running" },
  { label: "Validate", detail: "Persona interviews", status: "queued" },
];

export function HomeHero() {
  return (
    <section className="relative overflow-hidden px-6 pb-20 pt-36 sm:pb-28 sm:pt-40">
      <div
        aria-hidden
        className="ambient-orbit pointer-events-none absolute left-1/2 top-8 h-[34rem] w-[58rem] -translate-x-1/2 rounded-full opacity-80 blur-3xl"
        style={{
          background:
            "radial-gradient(circle at 30% 30%, rgba(45,212,191,0.28), transparent 42%), radial-gradient(circle at 68% 28%, rgba(251,191,36,0.12), transparent 35%), radial-gradient(circle at 50% 70%, rgba(251,113,133,0.12), transparent 38%)",
        }}
      />
      <div aria-hidden className="grid-backdrop pointer-events-none absolute inset-0 opacity-60" />

      <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[minmax(0,0.92fr)_minmax(26rem,1.08fr)]">
        <div className="max-w-2xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-secondary">
            <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
            The AI startup operator
          </span>

          <h1 className="text-balance mt-6 text-4xl font-semibold leading-[1.04] tracking-tight text-foreground sm:text-5xl lg:text-6xl">
            Turn a startup idea into an execution-ready MVP workspace
          </h1>

          <p className="text-balance mt-6 max-w-xl text-lg leading-relaxed text-secondary">
            bucks.ai researches the market, drafts the blueprint, deploys a
            starter build, validates it with customers, and coordinates the agents
            that keep the work moving.
          </p>

          <div className="mt-9 flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <Link
              href="/intake"
              className="inline-flex min-h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-accent-contrast shadow-soft transition-colors duration-200 hover:bg-accent-hover sm:w-auto"
            >
              Start building
              <span aria-hidden className="opacity-80">
                &#8594;
              </span>
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex min-h-12 w-full cursor-pointer items-center justify-center rounded-lg border border-border bg-surface px-6 py-3 text-sm font-medium text-secondary transition-colors duration-200 hover:border-border-strong hover:text-foreground sm:w-auto"
            >
              Open dashboard
            </Link>
          </div>

          <div className="mt-12 flex flex-wrap gap-y-2 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-muted">
            {capabilities.map((cap, index) => (
              <span key={cap} className="inline-flex items-center">
                {index > 0 ? (
                  <span aria-hidden className="mx-3 h-px w-4 bg-border-strong" />
                ) : null}
                {cap}
              </span>
            ))}
          </div>
        </div>

        <GlassCard className="p-2" innerClassName="rounded-[0.65rem] border border-border-subtle bg-elevated/85">
          <div className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-3">
            <div className="flex min-w-0 items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-status-blocked/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-status-pending/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-status-done/80" />
              <span className="ml-3 truncate font-mono text-xs text-muted">
                acme · execution workspace
              </span>
            </div>
            <StatusChip status="running" label="Live" />
          </div>

          <div className="p-5 sm:p-6">
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                ["Signal", "42%", "ICP confidence"],
                ["Deploy", "Live", "starter build"],
                ["Next", "Approve", "Vercel handoff"],
              ].map(([label, value, detail]) => (
                <div
                  key={label}
                  className="rounded-lg border border-border bg-background/70 p-3"
                >
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
                    {label}
                  </p>
                  <p className="mt-2 text-lg font-semibold tracking-tight text-foreground">
                    {value}
                  </p>
                  <p className="mt-1 text-xs text-secondary">{detail}</p>
                </div>
              ))}
            </div>

            <AnimatedPipeline stages={stages} className="mt-8" />

            <div className="mt-7 rounded-xl border border-accent/25 bg-accent/10 p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-accent-bright">
                AI recommendation
              </p>
              <p className="mt-2 text-sm font-semibold text-foreground">
                Approve deploy permissions, then run validation interviews.
              </p>
              <p className="mt-1.5 text-sm leading-6 text-secondary">
                The workspace is ready to move from starter build to customer
                signal without losing the founder approval boundary.
              </p>
            </div>
          </div>
        </GlassCard>
      </div>
    </section>
  );
}
