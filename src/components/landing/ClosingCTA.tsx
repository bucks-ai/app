import Link from "next/link";

export function ClosingCTA() {
  return (
    <section className="px-6 py-24 sm:py-32">
      <div
        className="relative mx-auto max-w-4xl overflow-hidden rounded-card border border-border bg-surface px-6 py-16 text-center sm:px-12"
        style={{ borderRadius: "var(--radius)" }}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-48"
          style={{ background: "var(--glow)" }}
        />
        <div className="relative">
          <h2 className="text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            Start with your idea
          </h2>
          <p className="text-balance mx-auto mt-4 max-w-md text-base leading-relaxed text-secondary">
            Hand bucks.ai a sentence and a budget. Get back research, a
            blueprint, a live deploy, and a team of agents.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/intake"
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-medium text-accent-contrast shadow-soft transition-colors hover:bg-accent-hover sm:w-auto"
            >
              Start building
              <span aria-hidden className="opacity-80">
                &#8594;
              </span>
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex w-full items-center justify-center rounded-lg border border-border bg-background px-6 py-3 text-sm font-medium text-secondary transition-colors hover:text-foreground sm:w-auto"
            >
              Open dashboard
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
