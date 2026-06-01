const nodes = [
  { name: "Strategy", body: "Goals, scope, and the blueprint that guides every run." },
  { name: "Research", body: "Market, competitor, and customer signal gathered up front." },
  { name: "Deployment", body: "GitHub repo and Vercel deploy wired and shipped." },
  { name: "Validation", body: "Persona interviews and tests that confirm demand." },
  { name: "Safety", body: "Tool permissions and limits that keep agents in bounds." },
  { name: "Orchestration", body: "Agent runs coordinated toward the next action." },
];

export function SystemPreview() {
  return (
    <section
      className="border-y border-border-subtle bg-surface px-6 py-20 sm:py-28"
    >
      <div className="mx-auto max-w-6xl">
        <div className="max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-widest text-accent">
            The system
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            One operator, six working parts
          </h2>
          <p className="mt-4 text-base leading-relaxed text-secondary">
            Each node owns a slice of the work and hands off cleanly to the next.
          </p>
        </div>

        <div className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {nodes.map((node) => (
            <div
              key={node.name}
              className="group rounded-card border border-border bg-background p-6 transition-colors hover:border-accent/40"
              style={{ borderRadius: "var(--radius)" }}
            >
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-accent transition-colors group-hover:border-accent/40">
                  <span className="h-2 w-2 rounded-full bg-accent" />
                </span>
                <h3 className="text-base font-medium text-foreground">
                  {node.name}
                </h3>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-secondary">
                {node.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
