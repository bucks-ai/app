import { MissionConsole } from "@/components/landing/MissionConsole";
import { BackgroundAtmosphere } from "@/components/ui/BackgroundAtmosphere";
import { CTAButton } from "@/components/ui/CTAButton";

const capabilities = ["Strategy", "Research", "Validation", "Build", "Deploy", "Learn"];
const proofPoints = ["Founder-safe autonomy", "GitHub + Vercel orchestration", "Supabase-backed workspaces"];
const heroStats = [
  ["6", "agent lanes"],
  ["10", "workspace tabs"],
  ["3", "approval gates"],
];

export function HomeHero() {
  return (
    <section className="noise-backdrop light-field relative overflow-hidden px-6 pb-18 pt-32 sm:pb-24 sm:pt-40">
      <BackgroundAtmosphere intensity="strong" drift />

      <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[minmax(0,0.86fr)_minmax(27rem,1.14fr)]">
        <div className="min-w-0 max-w-2xl">
          <div className="inline-flex max-w-full items-center gap-2 rounded-full border border-accent/25 bg-accent/10 px-3 py-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-accent-bright shadow-[var(--shadow-soft)]">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent-bright" />
            <span className="hidden truncate sm:inline">
              AI-native execution control plane
            </span>
            <span className="truncate sm:hidden">AI execution control plane</span>
          </div>

          <h1 className="text-balance mt-7 text-5xl font-semibold leading-[0.98] tracking-tight text-foreground sm:text-6xl lg:text-7xl">
            AI Mission Control for founder-led MVPs.
          </h1>

          <p className="mt-6 max-w-xl text-lg leading-8 text-foreground-secondary">
            bucks.ai turns a software-business idea into a controlled operating
            loop: agents research, validate, build, deploy, and stop for human
            approval before anything risky leaves the workspace.
          </p>

          <div className="mt-9 flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <CTAButton href="/dashboard" arrow className="w-full sm:w-auto">
              Enter the console
            </CTAButton>
            <CTAButton
              href="#execution-loop"
              variant="secondary"
              className="w-full sm:w-auto"
            >
              See the execution loop
            </CTAButton>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            {proofPoints.map((point) => (
              <span
                key={point}
                className="rounded-full border border-border bg-surface/70 px-3 py-1.5 text-xs font-medium text-foreground-secondary shadow-[var(--shadow-soft)]"
              >
                {point}
              </span>
            ))}
          </div>

          <div className="mt-10 grid max-w-xl grid-cols-3 gap-2">
            {heroStats.map(([value, label]) => (
              <div
                key={label}
                className="rounded-lg border border-border bg-surface/70 px-3 py-3 shadow-[var(--shadow-soft)]"
              >
                <p className="font-mono text-2xl font-semibold text-foreground">
                  {value}
                </p>
                <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  {label}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-10 flex flex-wrap gap-y-2 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
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
            className="absolute -inset-6 rounded-[2rem] border border-accent/15 bg-[radial-gradient(circle_at_20%_0%,var(--accent-soft),transparent_55%),linear-gradient(135deg,rgba(255,255,255,0.05),transparent)] blur-sm"
          />
          <div
            aria-hidden
            className="absolute -right-5 top-8 hidden rounded-xl border border-accent-blue/25 bg-background/75 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-accent-blue shadow-[var(--shadow-glass)] backdrop-blur md:block"
          >
            preview ready
          </div>
          <div
            aria-hidden
            className="absolute -left-4 bottom-10 hidden rounded-xl border border-warning/25 bg-background/75 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-warning shadow-[var(--shadow-glass)] backdrop-blur md:block"
          >
            approval gated
          </div>
          <MissionConsole compact />
        </div>
      </div>

      <div
        aria-hidden
        className="premium-divider relative mx-auto mt-16 h-px max-w-6xl"
      />
    </section>
  );
}
