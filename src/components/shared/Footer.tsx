import Link from "next/link";

const pipeline = ["Research", "Build", "Deploy", "Validate", "Agents"];

export function Footer() {
  return (
    <footer className="relative overflow-hidden border-t border-border/70 bg-background px-6 py-12">
      <div aria-hidden className="grid-backdrop pointer-events-none absolute inset-0 opacity-30" />
      <div className="mx-auto max-w-6xl">
        <div className="glass-surface relative flex flex-col items-center justify-between gap-8 rounded-card p-6 sm:flex-row sm:items-start">
          <div>
            <Link
              href="/"
              className="font-display text-sm font-semibold text-foreground"
            >
              bucks<span className="text-accent">.ai</span>
            </Link>
            <p className="mt-2 max-w-xs text-xs leading-relaxed text-muted">
              The AI startup operator. One sentence in, a launched MVP
              workspace out.
            </p>
          </div>

          <nav aria-label="Footer" className="flex flex-wrap items-center justify-center gap-3 sm:gap-6">
            <Link
              href="/intake"
              className="inline-flex min-h-11 items-center text-xs text-secondary transition-colors duration-200 hover:text-foreground"
            >
              Start building
            </Link>
            <Link
              href="/tools"
              className="inline-flex min-h-11 items-center text-xs text-secondary transition-colors duration-200 hover:text-foreground"
            >
              Tool registry
            </Link>
            <Link
              href="/#how-it-works"
              className="inline-flex min-h-11 items-center text-xs text-secondary transition-colors duration-200 hover:text-foreground"
            >
              How it works
            </Link>
          </nav>
        </div>

        {/* pipeline signature */}
        <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-border-subtle pt-6 sm:flex-row">
          <div className="flex flex-wrap items-center justify-center font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
            {pipeline.map((stage, i) => (
              <span key={stage} className="inline-flex items-center">
                {i > 0 && (
                  <span aria-hidden className="mx-2.5 h-px w-3 bg-border" />
                )}
                {stage}
              </span>
            ))}
          </div>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            © {new Date().getFullYear()} bucks.ai
          </span>
        </div>
      </div>
    </footer>
  );
}
