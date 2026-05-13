const TIMELINE = [
  {
    day: "Day 0",
    phase: "Intake",
    actions: [
      "Founder submits idea, budget, and limits",
      "Blueprint generated — stack, pricing, 30-day plan",
      "Founder reviews and approves or adjusts",
    ],
  },
  {
    day: "Days 1–3",
    phase: "Foundation",
    actions: [
      "GitHub repo initialized",
      "Vercel and Supabase provisioned",
      "Core data model scaffolded",
    ],
  },
  {
    day: "Days 4–8",
    phase: "MVP Build",
    actions: [
      "Core product features implemented",
      "PostHog event tracking wired",
      "First deploy pushed to production URL",
    ],
  },
  {
    day: "Days 9–14",
    phase: "Go-to-Market",
    actions: [
      "Landing page copy generated and deployed",
      "ICP prospect list sourced from Apollo",
      "First outreach batch drafted — awaiting founder approval",
    ],
  },
  {
    day: "Days 15–30",
    phase: "Operating Mode",
    actions: [
      "Outreach running within approved limits",
      "Metric digest delivered weekly",
      "Improvements proposed, approved, shipped",
    ],
  },
];

export function LaunchTimeline() {
  return (
    <section className="py-24" style={{ background: "#0F0F0F" }}>
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-4">
          <span
            className="font-mono text-xs uppercase tracking-widest"
            style={{ color: "#4F46E5" }}
          >
            Launch Timeline
          </span>
        </div>
        <h2
          className="mb-2 text-4xl font-semibold tracking-tight"
          style={{ color: "#F0F0F0" }}
        >
          Day 0 to operating company.
        </h2>
        <p className="mb-3 max-w-xl text-lg" style={{ color: "#888888" }}>
          An example path for an AI software business.
        </p>
        <p
          className="mb-16 max-w-xl text-sm"
          style={{ color: "#888888", opacity: 0.6 }}
        >
          Actual timelines vary by product complexity, scope, and founder
          decisions. This is illustrative, not a guarantee.
        </p>

        <div className="relative">
          {/* Vertical line */}
          <div
            className="absolute left-[88px] top-0 hidden h-full w-px lg:block"
            style={{ background: "#1C1C1C" }}
          />

          <div className="space-y-10">
            {TIMELINE.map(({ day, phase, actions }, i) => (
              <div key={day} className="relative flex gap-8">
                {/* Day label */}
                <div className="w-20 shrink-0 pt-1 text-right">
                  <div
                    className="font-mono text-xs font-semibold"
                    style={{ color: "#4F46E5" }}
                  >
                    {day}
                  </div>
                </div>

                {/* Dot */}
                <div className="relative hidden shrink-0 lg:flex lg:items-start lg:justify-center lg:pt-2">
                  <div
                    className="h-2.5 w-2.5 rounded-full border-2"
                    style={{
                      borderColor: "#4F46E5",
                      background: i === 0 ? "#4F46E5" : "#080808",
                    }}
                  />
                </div>

                {/* Content */}
                <div
                  className="flex-1 rounded-xl border p-5"
                  style={{
                    background: "#080808",
                    borderColor: "#1C1C1C",
                  }}
                >
                  <div
                    className="mb-3 text-sm font-semibold"
                    style={{ color: "#F0F0F0" }}
                  >
                    {phase}
                  </div>
                  <ul className="space-y-2">
                    {actions.map((action) => (
                      <li
                        key={action}
                        className="flex items-start gap-2 text-xs"
                        style={{ color: "#888888" }}
                      >
                        <span style={{ color: "#4F46E5" }}>&#8250;</span>
                        {action}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
