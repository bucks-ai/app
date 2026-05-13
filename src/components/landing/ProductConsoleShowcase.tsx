const AGENTS = [
  { name: "BlueprintAgent", status: "idle", dept: "Planning" },
  { name: "CodeAgent", status: "running", dept: "Build" },
  { name: "DeployAgent", status: "done", dept: "Build" },
  { name: "MarketingAgent", status: "running", dept: "Growth" },
  { name: "ProspectAgent", status: "running", dept: "Sales" },
  { name: "OutreachAgent", status: "queued", dept: "Sales" },
  { name: "MonitorAgent", status: "running", dept: "Ops" },
];

const LOG_ENTRIES = [
  { time: "09:14:02", agent: "DeployAgent", msg: "MVP deployed to acme.vercel.app" },
  { time: "09:14:18", agent: "MarketingAgent", msg: "Landing page copy variant B generated" },
  { time: "09:15:33", agent: "ProspectAgent", msg: "47 ICP matches sourced from Apollo" },
  { time: "09:16:01", agent: "MonitorAgent", msg: "234 events ingested — no anomalies" },
  { time: "09:17:44", agent: "OutreachAgent", msg: "Outreach batch queued: 12 prospects" },
  { time: "09:18:09", agent: "CodeAgent", msg: "Webhook handler added — tests passing" },
];

const FOUNDER_QUEUE = [
  { priority: "HIGH", item: "Approve outreach batch before send" },
  { priority: "MED", item: "Review copy variant B vs A" },
  { priority: "LOW", item: "Confirm Stripe keys to unlock billing" },
];

const STATUS_COLOR: Record<string, string> = {
  running: "#4F46E5",
  done: "#22c55e",
  idle: "#888888",
  queued: "#f59e0b",
};

export function ProductConsoleShowcase() {
  return (
    <section
      id="execution-model"
      className="py-24"
      style={{ background: "#0F0F0F" }}
    >
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-4">
          <span
            className="font-mono text-xs uppercase tracking-widest"
            style={{ color: "#4F46E5" }}
          >
            Mission Control
          </span>
        </div>
        <h2
          className="mb-4 text-4xl font-semibold tracking-tight"
          style={{ color: "#F0F0F0" }}
        >
          One console. Every moving part.
        </h2>
        <p className="mb-12 max-w-xl text-lg" style={{ color: "#888888" }}>
          The operator console surfaces your agent roster, execution log, and
          founder queue in real time.
        </p>

        <div
          className="overflow-hidden rounded-xl border font-mono text-xs"
          style={{
            background: "#080808",
            borderColor: "#1C1C1C",
            boxShadow: "0 32px 64px rgba(0,0,0,0.6)",
          }}
        >
          {/* Console title bar */}
          <div
            className="flex items-center gap-3 border-b px-4 py-3"
            style={{ borderColor: "#1C1C1C", background: "#0F0F0F" }}
          >
            <div className="flex gap-1.5">
              <div className="h-2.5 w-2.5 rounded-full" style={{ background: "#1C1C1C" }} />
              <div className="h-2.5 w-2.5 rounded-full" style={{ background: "#1C1C1C" }} />
              <div className="h-2.5 w-2.5 rounded-full" style={{ background: "#1C1C1C" }} />
            </div>
            <span style={{ color: "#888888" }}>bucks.ai — Acme Analytics — Mission Control</span>
          </div>

          {/* Three panels */}
          <div className="grid divide-x lg:grid-cols-3" style={{ borderColor: "#1C1C1C" }}>
            {/* Panel 1: Agent roster */}
            <div className="p-4">
              <div
                className="mb-3 uppercase tracking-widest"
                style={{ color: "#888888" }}
              >
                Agent Roster
              </div>
              <div className="space-y-2">
                {AGENTS.map(({ name, status, dept }) => (
                  <div
                    key={name}
                    className="flex items-center justify-between rounded border px-2 py-1.5"
                    style={{ borderColor: "#1C1C1C", background: "#0F0F0F" }}
                  >
                    <div>
                      <div style={{ color: "#F0F0F0" }}>{name}</div>
                      <div style={{ color: "#888888" }}>{dept}</div>
                    </div>
                    <div
                      className="rounded px-1.5 py-0.5"
                      style={{
                        background: `${STATUS_COLOR[status]}18`,
                        color: STATUS_COLOR[status],
                      }}
                    >
                      {status}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Panel 2: Execution log */}
            <div className="p-4">
              <div
                className="mb-3 uppercase tracking-widest"
                style={{ color: "#888888" }}
              >
                Execution Log
              </div>
              <div className="space-y-2">
                {LOG_ENTRIES.map(({ time, agent, msg }) => (
                  <div key={time + agent} className="leading-tight">
                    <div className="flex items-center gap-2">
                      <span style={{ color: "#888888" }}>{time}</span>
                      <span style={{ color: "#4F46E5" }}>[{agent}]</span>
                    </div>
                    <div className="pl-2" style={{ color: "#F0F0F0" }}>
                      {msg}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Panel 3: Founder queue */}
            <div className="p-4">
              <div
                className="mb-3 uppercase tracking-widest"
                style={{ color: "#888888" }}
              >
                Founder Queue
              </div>
              <div className="space-y-2">
                {FOUNDER_QUEUE.map(({ priority, item }) => (
                  <div
                    key={item}
                    className="rounded border p-3"
                    style={{ borderColor: "#1C1C1C", background: "#0F0F0F" }}
                  >
                    <div
                      className="mb-1"
                      style={{
                        color:
                          priority === "HIGH"
                            ? "#ef4444"
                            : priority === "MED"
                            ? "#f59e0b"
                            : "#888888",
                      }}
                    >
                      {priority}
                    </div>
                    <div style={{ color: "#F0F0F0" }}>{item}</div>
                  </div>
                ))}
              </div>
              <div
                className="mt-4 rounded border p-3"
                style={{ borderColor: "#1C1C1C" }}
              >
                <div style={{ color: "#888888" }}>Awaiting your decision</div>
                <div className="mt-1" style={{ color: "#4F46E5" }}>
                  3 items pending
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
