"use client";

import { useId, useState } from "react";
import { SoftObject } from "@/components/ui/SoftObject";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { toolRegistry } from "@/lib/tool-registry";

type Phase = {
  key: string;
  label: string;
  agent: string;
  summary: string;
  /** Permission boundary, verbatim from the agent charter. */
  permissions: string[];
  /** Registry categories this phase actually draws on. */
  categories: string[];
};

/*
  The six phases are the six agents — this is not an invented taxonomy. Each
  one lists the permission boundary it operates under and pulls its tools
  live from the registry by category, so the panel cannot drift out of sync
  with what the product actually ships.
*/
const PHASES: Phase[] = [
  {
    key: "strategy",
    label: "Strategy",
    agent: "Strategy Agent",
    summary:
      "Converts the founder brief into a wedge, a target customer, a pricing constraint, and one measurable goal the rest of the loop optimises for.",
    permissions: ["read blueprint", "write strategy", "request approval"],
    categories: ["AI Model"],
  },
  {
    key: "research",
    label: "Research",
    agent: "Research Agent",
    summary:
      "Maps competitors, segments, buyer budgets, and risks before anything gets built, so validation tests bets instead of guesses.",
    permissions: ["read web", "write evidence", "no outbound"],
    categories: ["AI Model", "Analytics", "Monitoring"],
  },
  {
    key: "validation",
    label: "Validation",
    agent: "Validation Agent",
    summary:
      "Drafts interview scripts, persona assumptions, and pass/fail gates. Outbound stays drafted until a founder reads and approves it.",
    permissions: ["draft outreach", "write hypotheses", "approval gated"],
    categories: ["Outreach", "CRM"],
  },
  {
    key: "build",
    label: "Build",
    agent: "Build Agent",
    summary:
      "Turns approved scope into scoped GitHub issues with acceptance criteria — sized to the smallest preview that can produce a learning signal.",
    permissions: ["prepare repo", "write issues", "no production push"],
    categories: ["Code", "Database", "Auth"],
  },
  {
    key: "deploy",
    label: "Deploy",
    agent: "Deploy Agent",
    summary:
      "Prepares Vercel previews with rollback notes attached. Nothing goes public until the founder clears the release gate.",
    permissions: ["read deploys", "prepare preview", "human approve"],
    categories: ["Deployment", "Domains"],
  },
  {
    key: "learn",
    label: "Learn",
    agent: "Learning Agent",
    summary:
      "Folds validation results and telemetry back into the decision log, so the loop re-plans instead of letting the strategy go stale.",
    permissions: ["read metrics", "write next action", "no billing access"],
    categories: ["Analytics", "Payments", "Ads", "Marketing", "Automation"],
  },
];

function toolsFor(phase: Phase) {
  return toolRegistry
    .filter((t) => phase.categories.includes(t.category))
    .slice(0, 7);
}

/**
 * The operating loop as a set of expandable phases.
 *
 * Pattern borrowed from Apple-style feature blocks: a stack of rounded pills
 * where exactly one is open, the rest collapse to a label and a `+`. Widths
 * are content-sized rather than a uniform column, which is what stops it
 * reading as another rigid grid.
 *
 * Implemented as a single-select disclosure rather than a tablist: each pill
 * is a real button with `aria-expanded` controlling its own panel, so the
 * whole thing is keyboard-operable and screen readers get the open/closed
 * state without needing arrow-key roving focus.
 */
export function PhaseExplorer() {
  const [active, setActive] = useState(0);
  const uid = useId();
  const phase = PHASES[active];
  const tools = toolsFor(phase);

  return (
    <section className="relative px-6 py-20 sm:py-28">
      <div className="relative mx-auto max-w-6xl">
        <SectionHeader
          eyebrow="The operating loop"
          title="Six agents, one controlled hand-off"
          description="Each phase owns a job, runs under an explicit permission boundary, and hands state to the next. Open one to see the agent behind it and the tools it is allowed to touch."
        />

        <div className="mt-14 grid gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:items-start lg:gap-14">
          {/* The pill stack */}
          <ul className="flex flex-col gap-2.5">
            {PHASES.map((p, i) => {
              const open = i === active;
              return (
                <li key={p.key}>
                  <button
                    type="button"
                    onClick={() => setActive(i)}
                    aria-expanded={open}
                    aria-controls={`${uid}-panel`}
                    className={`interactive-surface group flex min-h-14 w-full items-center gap-3.5 rounded-full px-5 py-3 text-left sm:w-auto ${
                      open
                        ? "bg-[var(--surface-raised)] shadow-[var(--shadow-card)]"
                        : "bg-muted hover:bg-[var(--surface-raised)]"
                    }`}
                  >
                    <span
                      aria-hidden
                      className={`grid h-6 w-6 shrink-0 place-items-center rounded-full font-mono text-[11px] transition-colors ${
                        open
                          ? "bg-accent text-accent-contrast"
                          : "border border-edge-strong text-muted-foreground"
                      }`}
                    >
                      {open ? "" : "+"}
                    </span>
                    <span
                      className={`text-lg ${
                        open
                          ? "display-serif text-foreground"
                          : "font-medium text-foreground-secondary"
                      }`}
                    >
                      {p.label}
                    </span>
                    <span className="ml-auto pl-4 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          {/* The open phase */}
          <div id={`${uid}-panel`} className="flow-card relative overflow-hidden p-7 sm:p-9">
            <SoftObject
              size={13}
              seed={active + 1}
              drift={0}
              className="absolute -right-10 -top-10 opacity-60 sm:-right-6 sm:opacity-75"
            />

            <div className="relative">
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent-on-tint">
                {phase.agent}
              </p>
              <h3 className="display-serif mt-3 text-3xl text-foreground sm:text-4xl">
                {phase.label}
              </h3>
              <p className="mt-4 max-w-lg text-base leading-8 text-foreground-secondary">
                {phase.summary}
              </p>

              <p className="mt-8 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                Permission boundary
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {phase.permissions.map((perm) => (
                  <span
                    key={perm}
                    className="rounded-full bg-accent/12 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-accent-on-tint"
                  >
                    {perm}
                  </span>
                ))}
              </div>

              <p className="mt-8 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                Tools this phase can reach
              </p>
              <div className="mt-3 flex flex-wrap gap-2.5">
                {tools.map((t) => (
                  <span
                    key={t.name}
                    className="inline-flex items-center gap-2.5 rounded-full bg-muted py-1.5 pl-1.5 pr-4"
                  >
                    <span
                      aria-hidden
                      className="grid h-7 w-7 place-items-center rounded-full bg-[image:var(--cta-gradient)] font-mono text-[11px] font-semibold text-accent-contrast shadow-[var(--shadow-soft)]"
                    >
                      {t.name.slice(0, 1)}
                    </span>
                    <span className="text-sm text-foreground-secondary">{t.name}</span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
