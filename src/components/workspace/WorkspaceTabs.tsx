"use client";

export type TabKey =
  | "overview"
  | "research"
  | "actions"
  | "build"
  | "deploy"
  | "validation"
  | "team"
  | "tools"
  | "activity"
  | "settings";

export const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "research", label: "Research" },
  { key: "actions", label: "Actions" },
  { key: "build", label: "Build" },
  { key: "deploy", label: "Deploy" },
  { key: "validation", label: "Validation" },
  { key: "team", label: "Team" },
  { key: "tools", label: "Tools" },
  { key: "activity", label: "Activity" },
  { key: "settings", label: "Settings" },
];

type WorkspaceTabsProps = {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  badgeCounts?: Partial<Record<TabKey, number>>;
  className?: string;
};

export function WorkspaceTabs({
  activeTab,
  onTabChange,
  badgeCounts,
  className = "",
}: WorkspaceTabsProps) {
  return (
    <div className={`min-w-0 flex-1 ${className}`}>
      <div className="flex gap-2 overflow-x-auto px-4 py-2 sm:px-6" style={{ scrollbarWidth: "none" }}>
        {TABS.map((tab) => {
          const count = badgeCounts?.[tab.key];
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onTabChange(tab.key)}
              className={`relative flex min-h-11 shrink-0 items-center gap-1.5 rounded-lg border px-3 py-2 font-mono text-xs uppercase tracking-[0.16em] transition-colors ${
                isActive
                  ? "border-accent/45 bg-accent/12 text-accent"
                  : "border-transparent text-muted-foreground hover:border-border hover:bg-elevated hover:text-foreground-secondary"
              }`}
              aria-current={isActive ? "page" : undefined}
            >
              {tab.label}
              {count && count > 0 ? (
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                    tab.key === "actions"
                      ? "bg-warning/20 text-warning"
                      : "bg-accent/20 text-accent"
                  }`}
                >
                  {count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
