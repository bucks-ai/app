import { AgentCard, type AgentCardData } from "@/components/landing/AgentCard";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeader } from "@/components/ui/SectionHeader";

const agents: AgentCardData[] = [
  {
    name: "Strategy Agent",
    purpose: "Converts a founder brief into a business model, wedge, constraints, and measurable operating plan.",
    permissions: ["read blueprint", "write strategy", "request approval"],
    state: "Complete",
    lastRun: "priced wedge and ICP in 04m 12s",
  },
  {
    name: "Research Agent",
    purpose: "Maps competitors, market evidence, buyer budgets, risks, and customer segments before build starts.",
    permissions: ["read web", "write evidence", "no outbound"],
    state: "Running",
    lastRun: "clustered 31 market signals",
  },
  {
    name: "Validation Agent",
    purpose: "Creates customer test plans, interview scripts, persona assumptions, and validation gates.",
    permissions: ["draft outreach", "write hypotheses", "approval gated"],
    state: "Waiting",
    lastRun: "queued 12 founder interviews",
  },
  {
    name: "Build Agent",
    purpose: "Turns approved scope into GitHub tasks, scaffold decisions, acceptance criteria, and deploy steps.",
    permissions: ["prepare repo", "write issues", "no production push"],
    state: "Waiting",
    lastRun: "prepared preview task",
  },
  {
    name: "Deploy Agent",
    purpose: "Coordinates Vercel preview readiness, deployment state, rollback notes, and release checkpoints.",
    permissions: ["read deploys", "prepare preview", "human approve"],
    state: "Blocked",
    lastRun: "paused public preview",
  },
  {
    name: "Learning Agent",
    purpose: "Reads validation outcomes and updates the next action loop instead of letting a plan go stale.",
    permissions: ["read metrics", "write next action", "no billing access"],
    state: "Complete",
    lastRun: "updated decision log",
  },
];

export function AgentTeamPreview() {
  return (
    <section className="relative overflow-hidden border-y border-border-subtle bg-surface/35 px-6 py-20 sm:py-28">
      <div aria-hidden className="grid-backdrop pointer-events-none absolute inset-0 opacity-35" />
      <div className="relative mx-auto max-w-6xl">
        <Reveal>
          <SectionHeader
            eyebrow="Agent Registry"
            title="Infrastructure-grade agents, not toy assistants"
            description="Each agent has a job, a permission boundary, a current state, and a traceable last run."
          />
        </Reveal>

        <div className="mt-12 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {agents.map((agent, index) => (
            <Reveal key={agent.name} delay={index * 70}>
              <AgentCard
                agent={agent}
                className={index === 1 ? "xl:-translate-y-3" : ""}
              />
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
