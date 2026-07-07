import { Reveal } from "@/components/ui/Reveal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { GlassCard } from "@/components/ui/GlassCard";

type Agent = {
  name: string;
  code: string;
  role: string;
  tag: string;
  /** phase color drawn from the pipeline the agent serves */
  color: string;
};

const agents: Agent[] = [
  {
    name: "Market Research Agent",
    code: "MR",
    role: "Sizes the opportunity and maps competitors.",
    tag: "Research",
    color: "var(--accent-bright)",
  },
  {
    name: "Scaffold Agent",
    code: "SC",
    role: "Generates the starter repo and deploy.",
    tag: "Build",
    color: "var(--status-done)",
  },
  {
    name: "Persona Agent",
    code: "PE",
    role: "Runs customer interviews to test demand.",
    tag: "Validate",
    color: "var(--risk-medium)",
  },
  {
    name: "Next Action Agent",
    code: "NA",
    role: "Reads the workspace and proposes the next move.",
    tag: "Guidance",
    color: "var(--status-blocked)",
  },
];

export function AgentTeamPreview() {
  return (
    <section className="px-6 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <SectionHeader
            eyebrow="Operating team"
            title="A team of agents, already on the job"
            description="Specialized agents handle the legwork and report back through the workspace."
          />
        </Reveal>

        <div className="mt-12 grid gap-4 sm:grid-cols-2">
          {agents.map((agent, i) => (
            <Reveal key={agent.name} delay={i * 80}>
              <GlassCard
                interactive
                delay={i * 0.05}
                className="h-full p-6"
                innerClassName="flex h-full items-start justify-between gap-4"
              >
                <div className="flex items-start gap-4">
                  <span
                    className="mt-0.5 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-md border font-mono text-xs font-semibold"
                    style={{
                      color: agent.color,
                      borderColor: `color-mix(in srgb, ${agent.color} 35%, transparent)`,
                      background: `color-mix(in srgb, ${agent.color} 10%, transparent)`,
                    }}
                  >
                    {agent.code}
                  </span>
                  <div>
                    <h3 className="text-base font-medium text-foreground">
                      {agent.name}
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-secondary">
                      {agent.role}
                    </p>
                    <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
                      Phase owner
                    </p>
                  </div>
                </div>
                <span
                  className="flex-shrink-0 rounded-full border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-wider"
                  style={{
                    color: agent.color,
                    borderColor: `color-mix(in srgb, ${agent.color} 30%, transparent)`,
                  }}
                >
                  {agent.tag}
                </span>
              </GlassCard>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
