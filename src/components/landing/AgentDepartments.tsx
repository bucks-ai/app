const DEPARTMENTS = [
  {
    id: "01",
    name: "Business Blueprint",
    description:
      "Converts your idea into a structured execution plan with stack selection, pricing model, go-to-market sequence, and 30-day milestone breakdown.",
    outputs: [
      "Tech stack decision doc",
      "Pricing model + unit economics",
      "30-day milestone plan",
      "Competitive differentiation memo",
    ],
  },
  {
    id: "02",
    name: "MVP Builder",
    description:
      "Writes, tests, and deploys production code to Vercel. Sets up Supabase, PostHog, and the full data layer. Ships the first version without you touching a terminal.",
    outputs: [
      "Production Next.js app on Vercel",
      "Supabase schema + migrations",
      "PostHog event tracking",
      "GitHub repo with CI",
    ],
  },
  {
    id: "03",
    name: "Marketing Brain",
    description:
      "Generates positioning copy, runs SEO configuration, writes email sequences, and schedules content based on what the analytics show is working.",
    outputs: [
      "Landing page copy variants",
      "Email drip sequence (5–7 messages)",
      "SEO metadata + sitemap",
      "Content calendar draft",
    ],
  },
  {
    id: "04",
    name: "Sales Pipeline",
    description:
      "Sources ICPs from Apollo, drafts personalized outreach via Gmail/Resend, tracks opens and replies, and escalates to you only when a prospect is hot.",
    outputs: [
      "ICP list from Apollo (50–200 leads)",
      "Personalized cold outreach drafts",
      "Reply tracking + follow-up logic",
      "Hot lead escalation to founder",
    ],
  },
  {
    id: "05",
    name: "Continuous Loop",
    description:
      "Monitors metrics daily, surfaces what changed and why, proposes improvements, and ships approved changes. The business keeps moving while you sleep.",
    outputs: [
      "Weekly metric digest",
      "Improvement proposals with rationale",
      "Approved changes auto-deployed",
      "Anomaly alerts with context",
    ],
  },
];

export function AgentDepartments() {
  return (
    <section className="py-24" style={{ background: "#0F0F0F" }}>
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-4">
          <span
            className="font-mono text-xs uppercase tracking-widest"
            style={{ color: "#4F46E5" }}
          >
            Agent Departments
          </span>
        </div>
        <h2
          className="mb-4 text-4xl font-semibold tracking-tight"
          style={{ color: "#F0F0F0" }}
        >
          Five operating units. One system.
        </h2>
        <p className="mb-16 max-w-xl text-lg" style={{ color: "#888888" }}>
          Each department runs a defined scope. They coordinate through a shared
          execution context — no manual handoffs.
        </p>

        <div className="grid gap-4 lg:grid-cols-1">
          {DEPARTMENTS.map((dept) => (
            <div
              key={dept.id}
              className="grid gap-6 rounded-xl border p-6 lg:grid-cols-3"
              style={{ background: "#080808", borderColor: "#1C1C1C" }}
            >
              {/* Left: id + name + description */}
              <div className="lg:col-span-2">
                <div className="mb-3 flex items-center gap-3">
                  <span
                    className="font-mono text-xs"
                    style={{ color: "#4F46E5" }}
                  >
                    {dept.id}
                  </span>
                  <h3
                    className="text-base font-semibold"
                    style={{ color: "#F0F0F0" }}
                  >
                    {dept.name}
                  </h3>
                </div>
                <p className="text-sm leading-relaxed" style={{ color: "#888888" }}>
                  {dept.description}
                </p>
              </div>

              {/* Right: outputs */}
              <div
                className="rounded-lg border p-4"
                style={{ background: "#0F0F0F", borderColor: "#1C1C1C" }}
              >
                <div
                  className="mb-3 font-mono text-xs uppercase tracking-widest"
                  style={{ color: "#888888" }}
                >
                  Outputs
                </div>
                <ul className="space-y-2">
                  {dept.outputs.map((output) => (
                    <li
                      key={output}
                      className="flex items-start gap-2 text-xs"
                      style={{ color: "#F0F0F0" }}
                    >
                      <span style={{ color: "#4F46E5" }}>&#8250;</span>
                      {output}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
