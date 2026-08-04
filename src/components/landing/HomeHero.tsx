import { FieldReadout } from "@/components/landing/FieldReadout";
import { MissionConsole } from "@/components/landing/MissionConsole";
import { CTAButton } from "@/components/ui/CTAButton";
import { SoftObject } from "@/components/ui/SoftObject";

const capabilities = ["Strategy", "Research", "Validation", "Build", "Deploy", "Learn"];
const proofPoints = [
  "Founder-safe autonomy",
  "GitHub + Vercel orchestration",
  "Supabase-backed workspaces",
];
const heroStats = [
  ["6", "agent lanes"],
  ["10", "workspace tabs"],
  ["3", "approval gates"],
];

export function HomeHero() {
  return (
    // No local background or aurora: <PageField /> owns the atmosphere for the
    // whole route, so the hero dissolves into the page instead of sitting in
    // its own lit box.
    //
    // overflow-clip: the decorative object below is positioned past the right
    // edge on purpose, and without clipping it widened the document past the
    // viewport, giving every page a horizontal scrollbar at mobile widths.
    <section className="relative overflow-clip px-6 pb-24 pt-36 sm:pb-32 sm:pt-44">
      {/* The one soft, organic form in an otherwise structured page. It
          bleeds off the right edge so it reads as an object in the field
          rather than an illustration in a slot.

          z-0, not -z-10: .page-field sits at z-index -1, so anything below
          that renders behind the whole atmosphere and is never seen. The
          grid below is a later sibling, so content still paints over this. */}
      <SoftObject
        size={17}
        className="absolute right-[-5rem] top-4 z-0 opacity-70 md:right-[-3rem] md:opacity-85 lg:right-[1rem]"
      />
      <div className="relative mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-[minmax(0,0.92fr)_minmax(26rem,1.08fr)] lg:gap-16">
        <div className="min-w-0 max-w-2xl">
          <div className="inline-flex max-w-full items-center gap-2 rounded-full border border-accent/20 bg-accent/[0.07] px-3.5 py-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-accent-bright">
            <span
              aria-hidden
              className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent-bright"
            />
            <span className="hidden truncate sm:inline">
              AI-native execution control plane
            </span>
            <span className="truncate sm:hidden">AI execution control plane</span>
          </div>

          <h1 className="display-xl text-balance mt-8 text-6xl text-foreground sm:text-7xl lg:text-[4.75rem]">
            Mission control for{" "}
            {/* nowrap: the hyphen in "founder-led" is a legal break point and
                the serif split it across two lines. */}
            <span className="display-accent whitespace-nowrap">founder-led</span>{" "}
            MVPs.
          </h1>

          <p className="mt-7 max-w-lg text-lg leading-9 text-foreground-secondary">
            bucks.ai turns a software-business idea into a controlled operating
            loop: agents research, validate, build, deploy, and stop for human
            approval before anything risky leaves the workspace.
          </p>

          <div className="mt-10 flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
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

          {/* Stats were three bordered tiles; boxes inside a hero are exactly
              the rigidity being removed. Same information, carried by type
              hierarchy and a single hairline instead. */}
          <div className="mt-12 flex flex-wrap items-start gap-x-10 gap-y-6">
            {heroStats.map(([value, label]) => (
              <div key={label}>
                <p className="font-mono text-3xl font-semibold text-foreground">
                  {value}
                </p>
                <p className="mt-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  {label}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-10 flex flex-wrap gap-2">
            {proofPoints.map((point) => (
              <span
                key={point}
                className="rounded-full bg-muted px-3.5 py-1.5 text-xs font-medium text-foreground-secondary"
              >
                {point}
              </span>
            ))}
          </div>

          <div className="mt-10 flex flex-wrap gap-y-2 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
            {capabilities.map((capability, index) => (
              <span key={capability} className="inline-flex items-center">
                {index > 0 ? (
                  <span aria-hidden className="mx-3 h-px w-4 bg-edge-strong" />
                ) : null}
                {capability}
              </span>
            ))}
          </div>
        </div>

        <div className="relative min-w-0 lg:translate-y-4">
          {/* -inset-8 made this 16px wider than its column, which pushed the
              document 8px past a 320px viewport and introduced horizontal
              scroll. Only the vertical bleed is needed for the glow. */}
          <div
            aria-hidden
            className="absolute -inset-y-8 inset-x-0 rounded-[2.5rem] bg-[radial-gradient(circle_at_30%_0%,var(--accent-soft),transparent_60%)] blur-2xl"
          />
          {/* Two floating "preview ready" / "approval gated" chips used to sit
              here. The console behind them already shows both as tile labels,
              so they were duplicate decoration — and once surfaces became
              opaque they rendered clipped behind it anyway. */}
          <MissionConsole compact />
        </div>
      </div>

      <FieldReadout />
    </section>
  );
}
