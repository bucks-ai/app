"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusPill } from "@/components/ui/StatusPill";

type LoopStep = {
  key: string;
  label: string;
  headline: string;
  body: string;
  artifact: string;
  permission: string;
  logLine: string;
};

const steps: LoopStep[] = [
  {
    key: "idea",
    label: "Idea",
    headline: "One founder sentence enters the system",
    body: "The intake brief captures the idea, budget envelope, timeline, and the actions that stay human-only. That brief is the contract every agent runs against.",
    artifact: "founder brief",
    permission: "read brief",
    logLine: "Captured operating brief and execution constraints.",
  },
  {
    key: "strategy",
    label: "Strategy",
    headline: "Intent becomes an operating plan",
    body: "The Strategy Agent converts the brief into a wedge, target customer, pricing constraint, and a measurable goal the rest of the loop optimizes for.",
    artifact: "operating plan",
    permission: "write strategy",
    logLine: "Locked wedge, ICP, and launch constraints.",
  },
  {
    key: "research",
    label: "Research",
    headline: "Market evidence becomes a decision record",
    body: "Competitors, segments, buyer budgets, and risks are mapped before anything is built — so validation tests bets instead of guesses.",
    artifact: "evidence record",
    permission: "read web · write evidence",
    logLine: "Clustered market signals into validation bets.",
  },
  {
    key: "validation",
    label: "Validation",
    headline: "Customer tests run before the product hardens",
    body: "The Validation Agent drafts interview scripts, persona assumptions, and pass/fail gates. Outbound stays drafted until a founder approves it.",
    artifact: "validation plan",
    permission: "draft outreach · approval gated",
    logLine: "Created customer test plan; outreach held for approval.",
  },
  {
    key: "build",
    label: "Build",
    headline: "Approved scope becomes GitHub tasks",
    body: "Scoped issues with acceptance criteria and scaffold decisions — sized to the smallest preview that can produce a learning signal.",
    artifact: "scoped preview task",
    permission: "write issues · no production push",
    logLine: "Prepared GitHub issue with acceptance criteria.",
  },
  {
    key: "deploy",
    label: "Deploy",
    headline: "Previews ship behind a checkpoint",
    body: "Vercel previews are prepared with rollback notes attached. Nothing goes public until the founder clears the release gate.",
    artifact: "gated preview",
    permission: "prepare preview · human approve",
    logLine: "Preview deployment ready; awaiting founder approval.",
  },
  {
    key: "learn",
    label: "Learn",
    headline: "Outcomes update the next action",
    body: "Validation results and telemetry are folded back into the decision log, so the loop re-plans instead of letting the strategy go stale.",
    artifact: "decision log",
    permission: "read metrics · write next action",
    logLine: "Captured learning signal; updated next action.",
  },
];

function stateFor(index: number, active: number) {
  if (index < active) return "done" as const;
  if (index === active) return "running" as const;
  return "queued" as const;
}

/** Sticky console that re-renders as the reader scrolls the steps. */
function LoopConsole({ active }: { active: number }) {
  const reducedMotion = useReducedMotion();
  const step = steps[active];

  return (
    <div className="glass-surface glass-highlight relative overflow-hidden rounded-card">
      <div className="relative z-10">
        <div className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-3">
          <span className="font-mono text-xs text-muted-foreground">
            execution-loop · step {String(active + 1).padStart(2, "0")}/07
          </span>
          <StatusPill label={step.label} variant="accent" />
        </div>

        {/* stage map — states derive from scroll position */}
        <div className="border-b border-border-subtle px-4 py-4">
          <ol className="flex items-center" aria-label="Loop stages">
            {steps.map((s, i) => {
              const state = stateFor(i, active);
              return (
                <li key={s.key} className="flex flex-1 items-center last:flex-none">
                  <span
                    className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border font-mono text-[11px] ${
                      state === "done"
                        ? "border-status-done/45 text-status-done"
                        : state === "running"
                          ? "pulse-ring border-accent bg-accent-soft text-accent-bright"
                          : "border-border text-muted-foreground"
                    }`}
                    title={s.label}
                  >
                    {state === "done" ? (
                      <svg
                        aria-hidden
                        viewBox="0 0 12 12"
                        className="h-2.5 w-2.5"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M2 6.5 4.8 9 10 3.5" />
                      </svg>
                    ) : (
                      i + 1
                    )}
                  </span>
                  {i < steps.length - 1 ? (
                    <span
                      aria-hidden
                      className={`mx-1 h-px flex-1 ${
                        state === "done"
                          ? "rail-line-done"
                          : state === "running"
                            ? "flow-line-x"
                            : "rail-line-idle"
                      }`}
                    />
                  ) : null}
                </li>
              );
            })}
          </ol>
        </div>

        {/* active step detail — crossfades on change */}
        <div className="relative min-h-[13rem] px-4 py-4 sm:px-5">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={step.key}
              initial={reducedMotion ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reducedMotion ? undefined : { opacity: 0, y: -8 }}
              transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="flow-well p-3.5">
                  <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                    Artifact
                  </p>
                  <p className="mt-2 text-sm font-semibold text-foreground">
                    {step.artifact}
                  </p>
                </div>
                <div className="flow-well p-3.5">
                  <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                    Permissions
                  </p>
                  <p className="mt-2 font-mono text-xs leading-5 text-foreground-secondary">
                    {step.permission}
                  </p>
                </div>
              </div>

              <div className="flow-well mt-3 p-3.5">
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Last log line
                </p>
                <p className="mt-2 grid grid-cols-[3rem_minmax(0,1fr)] gap-2 text-sm leading-5 text-foreground-secondary">
                  <span className="font-mono text-[11px] text-muted-foreground">
                    {`0${active + 2}:1${active}`}
                  </span>
                  <span>
                    <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-accent-bright">
                      {step.key}
                    </span>{" "}
                    {step.logLine}
                  </span>
                </p>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

export function ExecutionLoop() {
  const [active, setActive] = useState(0);
  const stepRefs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;

    // The step whose block crosses the middle band of the viewport wins.
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const index = stepRefs.current.indexOf(entry.target as HTMLLIElement);
          if (index >= 0) setActive(index);
        }
      },
      { rootMargin: "-42% 0px -42% 0px", threshold: 0 }
    );

    for (const node of stepRefs.current) {
      if (node) observer.observe(node);
    }
    return () => observer.disconnect();
  }, []);

  return (
    <section
      id="execution-loop"
      className="relative overflow-clip px-6 py-20 sm:py-28"
    >
      <div className="relative mx-auto max-w-6xl">
        <SectionHeader
          eyebrow="Execution Loop"
          title="Idea to learning signal, one controlled loop"
          description="Scroll the loop. Each stage produces an artifact, runs under explicit permissions, and hands state to the next stage — the console tracks where you are."
        />

        {/* Seven bordered cards of identical weight stacked in one column
            read as a filing cabinet and gave the scroll story no focus.
            Only the active step draws a surface now; the rest are separated
            by space and a left rule, so the eye tracks the one that's live. */}
        <div className="mt-14 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(24rem,0.95fr)]">
          <ol className="space-y-2">
            {steps.map((step, index) => {
              const isActive = index === active;
              return (
                <li
                  key={step.key}
                  ref={(node) => {
                    stepRefs.current[index] = node;
                  }}
                  // De-emphasis is carried by the surface and the left rule,
                  // never by opacity. A wrapper `opacity-60` multiplied every
                  // descendant's contrast — the body copy landed at 2.8:1 in
                  // light mode — and `hover:opacity-90` does nothing for
                  // keyboard or touch. This is real content, so it stays at
                  // full opacity and simply doesn't get the active treatment.
                  className={`rounded-card border-l-2 py-5 pl-6 pr-5 transition-all duration-500 sm:py-6 ${
                    isActive
                      ? "border-l-accent bg-[var(--surface-raised)] shadow-[var(--shadow-card)]"
                      : "border-l-edge-strong"
                  }`}
                  aria-current={isActive ? "step" : undefined}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p
                      className={`font-mono text-[11px] font-semibold uppercase tracking-[0.18em] ${
                        isActive ? "text-accent-bright" : "text-muted-foreground"
                      }`}
                    >
                      {String(index + 1).padStart(2, "0")} · {step.label}
                    </p>
                    {/* inline state so the story works without the console on mobile */}
                    <StatusPill
                      label={isActive ? "Active" : index < active ? "Complete" : "Queued"}
                      variant={isActive ? "accent" : index < active ? "success" : "neutral"}
                      className="lg:hidden"
                    />
                  </div>
                  <h3
                    className={`mt-3 text-xl font-semibold tracking-tight transition-colors duration-300 ${
                      isActive ? "text-foreground" : "text-foreground-secondary"
                    }`}
                  >
                    {step.headline}
                  </h3>
                  <p className="mt-2.5 text-sm leading-7 text-foreground-secondary">
                    {step.body}
                  </p>
                  <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground lg:hidden">
                    Artifact: <span className="text-foreground-secondary">{step.artifact}</span>
                  </p>
                </li>
              );
            })}
          </ol>

          <div className="hidden lg:block">
            <div className="sticky top-28">
              <LoopConsole active={active} />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
