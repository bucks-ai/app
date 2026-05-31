"use client";

export type TabKey =
  | "overview"
  | "research"
  | "actions"
  | "build"
  | "deploy"
  | "validation"
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
  { key: "tools", label: "Tools" },
  { key: "activity", label: "Activity" },
  { key: "settings", label: "Settings" },
];

type WorkspaceTabsProps = {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  badgeCounts?: Partial<Record<TabKey, number>>;
};

export function WorkspaceTabs({
  activeTab,
  onTabChange,
  badgeCounts,
}: WorkspaceTabsProps) {
  return (
    <div className="min-w-0 flex-1 bg-[#080808]">
      <div className="flex overflow-x-auto px-4 sm:px-6" style={{ scrollbarWidth: "none" }}>
        {TABS.map((tab) => {
          const count = badgeCounts?.[tab.key];
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onTabChange(tab.key)}
              className={`relative flex shrink-0 items-center gap-1.5 border-b-2 px-4 py-3 font-mono text-xs uppercase tracking-[0.18em] transition-colors ${
                isActive
                  ? "border-[#4F46E5] text-[#A5B4FC]"
                  : "border-transparent text-[#444] hover:text-[#888]"
              }`}
            >
              {tab.label}
              {count && count > 0 ? (
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                    tab.key === "actions"
                      ? "bg-[#F59E0B]/20 text-[#FCD34D]"
                      : "bg-[#4F46E5]/20 text-[#A5B4FC]"
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
