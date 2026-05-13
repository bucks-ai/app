export function OperatorConsoleMockup() {
  return (
    <div
      className="rounded-xl border font-mono text-sm"
      style={{
        background: "#0F0F0F",
        borderColor: "#1C1C1C",
        boxShadow: "0 0 0 1px #1C1C1C, 0 24px 48px rgba(0,0,0,0.6)",
      }}
    >
      {/* Title bar */}
      <div
        className="flex items-center justify-between border-b px-4 py-3"
        style={{ borderColor: "#1C1C1C" }}
      >
        <div className="flex items-center gap-2">
          <div className="h-2.5 w-2.5 rounded-full" style={{ background: "#4F46E5" }} />
          <span style={{ color: "#F0F0F0" }} className="text-xs font-medium tracking-wide">
            OPERATOR CONSOLE
          </span>
        </div>
        <span className="text-xs" style={{ color: "#888888" }}>
          live
        </span>
      </div>

      {/* Company header */}
      <div className="border-b px-4 py-4" style={{ borderColor: "#1C1C1C" }}>
        <div className="flex items-start justify-between">
          <div>
            <div className="text-base font-semibold" style={{ color: "#F0F0F0" }}>
              Acme Analytics
            </div>
            <div className="mt-0.5 text-xs" style={{ color: "#888888" }}>
              Building · Day 8 / 30
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs" style={{ color: "#888888" }}>
              7 agents active
            </div>
            <div className="mt-0.5 text-xs" style={{ color: "#888888" }}>
              Last action: 4s ago
            </div>
          </div>
        </div>
      </div>

      {/* Status rows */}
      <div className="divide-y" style={{ borderColor: "#1C1C1C" }}>
        {[
          { label: "MVP", status: "Live", detail: "acme.vercel.app", color: "#22c55e" },
          { label: "Marketing", status: "Running", detail: "847 leads", color: "#4F46E5" },
          { label: "Pipeline", status: "Active", detail: "12 prospects in sequence", color: "#4F46E5" },
          { label: "Analytics", status: "Wired", detail: "234 events/day", color: "#22c55e" },
        ].map(({ label, status, detail, color }) => (
          <div
            key={label}
            className="flex items-center justify-between px-4 py-3"
            style={{ borderColor: "#1C1C1C" }}
          >
            <span className="w-20 text-xs" style={{ color: "#888888" }}>
              {label}
            </span>
            <div className="flex items-center gap-1.5">
              <div
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: color }}
              />
              <span className="text-xs font-medium" style={{ color }}>
                {status}
              </span>
            </div>
            <span className="text-right text-xs" style={{ color: "#888888" }}>
              {detail}
            </span>
          </div>
        ))}
      </div>

      {/* Footer row */}
      <div
        className="flex items-center justify-between rounded-b-xl px-4 py-3"
        style={{ background: "#080808", borderTop: "1px solid #1C1C1C" }}
      >
        <span className="text-xs" style={{ color: "#888888" }}>
          Awaiting founder
        </span>
        <span
          className="rounded px-2 py-0.5 text-xs font-medium"
          style={{ background: "#1C1C1C", color: "#F0F0F0" }}
        >
          0 items
        </span>
      </div>
    </div>
  );
}
