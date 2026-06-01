const steps = [
  {
    n: "01",
    title: "Enter your idea",
    body: "Describe the product, your goal, budget, and any boundaries. That's the whole brief.",
  },
  {
    n: "02",
    title: "Generate research + blueprint",
    body: "bucks.ai scans the market, sizes the opportunity, and drafts a strategy you can edit.",
  },
  {
    n: "03",
    title: "Build & deploy the workspace",
    body: "It scaffolds the starter repo and ships a live deploy on GitHub and Vercel.",
  },
  {
    n: "04",
    title: "Validate with customers",
    body: "Persona interviews and agent runs pressure-test the idea and surface the next move.",
  },
];

export function WorkflowSteps() {
  return (
    <section id="how-it-works" className="px-6 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl">
        <div className="max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-widest text-accent">
            How it works
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            From a sentence to a working workspace
          </h2>
          <p className="mt-4 text-base leading-relaxed text-secondary">
            Four steps run end to end. You stay in control and step in only where
            judgment is needed.
          </p>
        </div>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step) => (
            <div
              key={step.n}
              className="rounded-card border border-border bg-surface p-6 transition-colors hover:border-accent/40"
              style={{ borderRadius: "var(--radius)" }}
            >
              <span className="font-mono text-sm text-muted">{step.n}</span>
              <h3 className="mt-4 text-base font-medium text-foreground">
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-secondary">
                {step.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
