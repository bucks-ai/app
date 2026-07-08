import Link from "next/link";
import { MissionConsole } from "@/components/landing/MissionConsole";

const capabilities = ["Strategy", "Research", "Validation", "Build", "Deploy", "Learn"];

export function HomeHero() {
  return (
    <section className="noise-backdrop relative overflow-hidden px-6 pb-20 pt-36 sm:pb-28 sm:pt-40">
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-10 h-[34rem] w-[70rem] -translate-x-1/2 rounded-full opacity-75 blur-3xl"
        style={{
          background:
            "radial-gradient(circle at 28% 35%, rgba(109,93,252,0.24), transparent 36%), radial-gradient(circle at 72% 24%, rgba(34,211,238,0.08), transparent 34%)",
        }}
      />
      <div aria-hidden className="grid-backdrop pointer-events-none absolute inset-0 opacity-55" />

      <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[minmax(0,0.88fr)_minmax(27rem,1.12fr)]">
        <div className="min-w-0 max-w-2xl">
          <div className="inline-flex max-w-full items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-secondary">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent-bright" />
            <span className="hidden truncate sm:inline">
              Autonomous execution layer for AI software teams
            </span>
            <span className="truncate sm:hidden">Autonomous execution layer</span>
          </div>

          <h1 className="text-balance mt-7 text-5xl font-semibold leading-[0.98] tracking-tight text-foreground sm:text-6xl lg:text-7xl">
            Your startup, operating itself.
          </h1>

          <p className="mt-6 max-w-xl text-lg leading-8 text-secondary">
            bucks.ai turns strategy, research, validation, build, and deployment
            into an operator-led execution loop with agent work, tool access, and
            human checkpoints in one console.
          </p>

          <div className="mt-9 flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <Link
              href="/dashboard"
              className="inline-flex min-h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-accent-contrast shadow-soft transition-colors duration-200 hover:bg-accent-hover sm:w-auto"
            >
              Enter the console
              <span aria-hidden className="opacity-80">
                &#8594;
              </span>
            </Link>
            <Link
              href="#execution-flow"
              className="inline-flex min-h-12 w-full cursor-pointer items-center justify-center rounded-lg border border-border bg-surface/70 px-6 py-3 text-sm font-medium text-secondary transition-colors duration-200 hover:border-accent/45 hover:text-foreground sm:w-auto"
            >
              View execution flow
            </Link>
          </div>

          <div className="mt-12 flex flex-wrap gap-y-2 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-muted">
            {capabilities.map((capability, index) => (
              <span key={capability} className="inline-flex items-center">
                {index > 0 ? (
                  <span aria-hidden className="mx-3 h-px w-4 bg-border-strong" />
                ) : null}
                {capability}
              </span>
            ))}
          </div>
        </div>

        <div className="relative min-w-0 lg:translate-y-4">
          <div
            aria-hidden
            className="absolute -inset-6 rounded-[2rem] border border-accent/15 bg-accent/5 blur-sm"
          />
          <MissionConsole compact />
        </div>
      </div>
    </section>
  );
}
