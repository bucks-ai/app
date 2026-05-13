const AUTO_ACTIONS = [
  "Build and deploy code",
  "Set up analytics",
  "Generate marketing content",
  "Source prospects",
  "Draft and run outreach within limits",
  "Monitor metrics",
  "Propose and ship improvements",
];

const HUMAN_ACTIONS = [
  "Sign legal documents",
  "Authorize payments",
  "Accept terms of service",
  "Enter bank, tax, or identity information",
  "Join sales calls",
  "Sign contracts",
];

export function AutonomyModel() {
  return (
    <section className="py-24" style={{ background: "#080808" }}>
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-4">
          <span
            className="font-mono text-xs uppercase tracking-widest"
            style={{ color: "#4F46E5" }}
          >
            Autonomy Model
          </span>
        </div>
        <h2
          className="mb-4 text-4xl font-semibold leading-tight tracking-tight"
          style={{ color: "#F0F0F0" }}
        >
          Autonomous by default.
          <br />
          Human where it matters.
        </h2>
        <p className="mb-16 max-w-xl text-lg" style={{ color: "#888888" }}>
          bucks.ai operates within a hard boundary between what it can do on
          its own and what requires a human decision.
        </p>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Auto column */}
          <div
            className="rounded-xl border p-6"
            style={{
              background: "#0F0F0F",
              borderColor: "#1C1C1C",
            }}
          >
            <div
              className="mb-1 inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-xs"
              style={{
                borderColor: "#1C1C1C",
                color: "#888888",
                background: "#080808",
              }}
            >
              <div
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: "#4F46E5" }}
              />
              bucks.ai acts automatically
            </div>
            <ul className="mt-5 space-y-3">
              {AUTO_ACTIONS.map((action) => (
                <li key={action} className="flex items-start gap-3">
                  <span
                    className="mt-0.5 select-none text-sm font-semibold"
                    style={{ color: "#4F46E5" }}
                  >
                    +
                  </span>
                  <span className="text-sm" style={{ color: "#F0F0F0" }}>
                    {action}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* Human column */}
          <div
            className="rounded-xl border p-6"
            style={{
              background: "#0F0F0F",
              borderColor: "#1C1C1C",
            }}
          >
            <div
              className="mb-1 inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-xs"
              style={{
                borderColor: "#1C1C1C",
                color: "#888888",
                background: "#080808",
              }}
            >
              <div
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: "#F0F0F0" }}
              />
              Only you can do
            </div>
            <ul className="mt-5 space-y-3">
              {HUMAN_ACTIONS.map((action) => (
                <li key={action} className="flex items-start gap-3">
                  <span
                    className="mt-0.5 select-none text-sm"
                    style={{ color: "#888888" }}
                  >
                    —
                  </span>
                  <span className="text-sm" style={{ color: "#F0F0F0" }}>
                    {action}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
