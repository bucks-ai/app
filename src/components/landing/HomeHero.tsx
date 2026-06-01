import Link from "next/link";

const capabilities = ["Research", "Build", "Deploy", "Validate", "Agents"];

export function HomeHero() {
  return (
    <section className="relative overflow-hidden px-6 pt-32 pb-20 sm:pt-36 sm:pb-28">
      {/* soft brand glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[480px]"
        style={{ background: "var(--glow)" }}
      />

      <div className="relative mx-auto flex max-w-3xl flex-col items-center text-center">
        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-secondary">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          The AI startup operator
        </span>

        <h1 className="text-balance mt-6 text-4xl font-semibold leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-6xl">
          Turn a startup idea into an
          <br className="hidden sm:block" /> execution-ready MVP workspace
        </h1>

        <p className="text-balance mt-6 max-w-xl text-lg leading-relaxed text-secondary">
          bucks.ai researches the market, drafts the blueprint, deploys a
          starter build, validates it with customers, and coordinates the agents
          that keep the work moving.
        </p>

        <div className="mt-9 flex w-full flex-col items-center justify-center gap-3 sm:w-auto sm:flex-row">
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
            className="inline-flex w-full items-center justify-center rounded-lg border border-border bg-surface px-6 py-3 text-sm font-medium text-secondary transition-colors hover:text-foreground sm:w-auto"
          >
            Open dashboard
          </Link>
        </div>

        {/* capability strip */}
        <div className="mt-12 flex flex-wrap items-center justify-center gap-x-2 gap-y-2 text-xs font-medium text-muted">
          {capabilities.map((cap, i) => (
            <span key={cap} className="inline-flex items-center gap-2">
              {i > 0 && <span className="text-border">·</span>}
              <span className="rounded-md px-1 py-0.5 tracking-wide uppercase">
                {cap}
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* product preview */}
      <div className="relative mx-auto mt-16 max-w-4xl">
        <HeroPreview />
      </div>
    </section>
  );
}

function HeroPreview() {
  const rows = [
    { label: "Research", detail: "Market + competitor scan", status: "Done" },
    { label: "Blueprint", detail: "Strategy & MVP scope", status: "Done" },
    { label: "Deploy", detail: "GitHub + Vercel starter", status: "Running" },
    { label: "Validate", detail: "Persona interviews", status: "Queued" },
  ];

  return (
    <div
      className="rounded-card border border-border bg-surface p-2 shadow-card"
      style={{ borderRadius: "var(--radius)" }}
    >
      <div className="rounded-[0.6rem] border border-border-subtle bg-elevated">
        {/* window chrome */}
        <div className="flex items-center gap-2 border-b border-border-subtle px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-border" />
          <span className="h-2.5 w-2.5 rounded-full bg-border" />
          <span className="h-2.5 w-2.5 rounded-full bg-border" />
          <span className="ml-3 text-xs text-muted">acme · execution workspace</span>
        </div>

        <div className="divide-y divide-border-subtle">
          {rows.map((row) => (
            <div
              key={row.label}
              className="flex items-center justify-between gap-4 px-4 py-3.5 sm:px-5"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">{row.label}</p>
                <p className="truncate text-xs text-muted">{row.detail}</p>
              </div>
              <StatusChip status={row.status} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const tone =
    status === "Done"
      ? "var(--success)"
      : status === "Running"
        ? "var(--accent)"
        : "var(--text-muted)";
  return (
    <span
      className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs font-medium text-secondary"
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: tone }}
      />
      {status}
    </span>
  );
}
