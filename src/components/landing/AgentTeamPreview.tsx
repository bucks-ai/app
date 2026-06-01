const agents = [
  {
    name: "Market Research Agent",
    role: "Sizes the opportunity and maps competitors.",
    tag: "Research",
  },
  {
    name: "Scaffold Agent",
    role: "Generates the starter repo and deploy.",
    tag: "Build",
  },
  {
    name: "Persona Agent",
    role: "Runs customer interviews to test demand.",
    tag: "Validate",
  },
  {
    name: "Next Action Agent",
    role: "Reads the workspace and proposes the next move.",
    tag: "Guidance",
  },
];

export function AgentTeamPreview() {
  return (
    <section className="px-6 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl">
        <div className="max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-widest text-accent">
            Operating team
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            A team of agents, already on the job
          </h2>
          <p className="mt-4 text-base leading-relaxed text-secondary">
            Specialized agents handle the legwork and report back through the
            workspace.
          </p>
        </div>

        <div className="mt-12 grid gap-3 sm:grid-cols-2">
          {agents.map((agent) => (
            <div
              key={agent.name}
              className="flex items-start justify-between gap-4 rounded-card border border-border bg-surface p-6 transition-colors hover:border-accent/40"
              style={{ borderRadius: "var(--radius)" }}
            >
              <div className="flex items-start gap-4">
                <span className="mt-0.5 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-accent-soft text-sm font-semibold text-accent">
                  {agent.name.charAt(0)}
                </span>
                <div>
                  <h3 className="text-base font-medium text-foreground">
                    {agent.name}
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-secondary">
                    {agent.role}
                  </p>
                </div>
              </div>
              <span className="flex-shrink-0 rounded-full border border-border px-2.5 py-1 text-xs font-medium text-muted">
                {agent.tag}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
