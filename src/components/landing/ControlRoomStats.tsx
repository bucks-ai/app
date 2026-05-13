const STATS = [
  { value: "47", label: "companies being built" },
  { value: "12,847", label: "agent actions today" },
  { value: "23", label: "MVPs shipped this month" },
];

export function ControlRoomStats() {
  return (
    <section
      className="border-y py-8"
      style={{ borderColor: "#1C1C1C", background: "#0F0F0F" }}
    >
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-6 text-center">
          <span
            className="rounded-full border px-3 py-1 font-mono text-xs uppercase tracking-widest"
            style={{ borderColor: "#1C1C1C", color: "#888888" }}
          >
            Demo operating snapshot
          </span>
        </div>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
          {STATS.map(({ value, label }) => (
            <div key={label} className="text-center">
              <div
                className="mb-1 font-mono text-3xl font-semibold"
                style={{ color: "#4F46E5" }}
              >
                {value}
              </div>
              <div className="text-sm" style={{ color: "#888888" }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
