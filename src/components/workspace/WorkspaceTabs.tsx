"use client";

import { useState } from "react";

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

export type TabGroup = "Plan" | "Build" | "Operate";

export const TABS: { key: TabKey; label: string; group: TabGroup }[] = [
  { key: "overview", label: "Overview", group: "Plan" },
  { key: "research", label: "Research", group: "Plan" },
  { key: "actions", label: "Actions", group: "Plan" },
  { key: "build", label: "Build", group: "Build" },
  { key: "deploy", label: "Deploy", group: "Build" },
  { key: "validation", label: "Validation", group: "Operate" },
  { key: "team", label: "Team", group: "Operate" },
  { key: "tools", label: "Tools", group: "Operate" },
  { key: "activity", label: "Activity", group: "Operate" },
  { key: "settings", label: "Settings", group: "Operate" },
];

export const TAB_GROUPS: TabGroup[] = ["Plan", "Build", "Operate"];

type WorkspaceTabsProps = {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  badgeCounts?: Partial<Record<TabKey, number>>;
  className?: string;
};

function groupOf(tab: TabKey): TabGroup {
  return TABS.find((t) => t.key === tab)?.group ?? "Plan";
}

/**
 * Mobile workspace navigation, two-tier.
 *
 * This was one horizontally-scrolling strip of all ten tabs — the overloaded
 * nav anti-pattern. Half the destinations sat off-screen with no affordance,
 * so finding anything meant swiping blind. Splitting into the same
 * Plan / Build / Operate groups the desktop sidebar already uses means at
 * most five items are ever on screen, both tiers fit at 375px without
 * horizontal scrolling, and the two layouts finally teach one mental model
 * instead of two.
 *
 * Choosing a group does not navigate — it only reveals that group's tabs, so
 * a mis-tap costs nothing.
 */
export function WorkspaceTabs({
  activeTab,
  onTabChange,
  badgeCounts,
  className = "",
}: WorkspaceTabsProps) {
  const [openGroup, setOpenGroup] = useState<TabGroup>(() => groupOf(activeTab));
  const [lastTab, setLastTab] = useState<TabKey>(activeTab);

  // Deep links and canvas nodes can land on a tab outside the open group, so
  // the visible tier has to follow the page rather than the last tap.
  // Adjusted during render rather than in an effect: this is derived state,
  // and an effect would paint the wrong group for a frame first.
  if (activeTab !== lastTab) {
    setLastTab(activeTab);
    setOpenGroup(groupOf(activeTab));
  }

  const visible = TABS.filter((t) => t.group === openGroup);

  const groupBadge = (group: TabGroup) =>
    TABS.filter((t) => t.group === group).reduce(
      (sum, t) => sum + (badgeCounts?.[t.key] ?? 0),
      0,
    );

  return (
    <div className={`min-w-0 flex-1 ${className}`}>
      <div className="flex gap-2 px-4 pt-2 sm:px-6">
        {TAB_GROUPS.map((group) => {
          const isOpen = group === openGroup;
          const count = groupBadge(group);
          return (
            <button
              key={group}
              type="button"
              onClick={() => setOpenGroup(group)}
              aria-pressed={isOpen}
              className={`flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-full px-3 py-2 font-mono text-[11px] uppercase tracking-[0.18em] transition-colors ${
                isOpen
                  ? "bg-accent/12 text-accent-on-tint"
                  : "bg-muted text-muted-foreground hover:text-foreground-secondary"
              }`}
            >
              {group}
              {count > 0 ? (
                <span className="rounded-full bg-warning/20 px-1.5 py-0.5 text-[11px] font-bold text-warning">
                  {count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      <div
        className="flex gap-2 overflow-x-auto px-4 py-2 sm:px-6"
        style={{ scrollbarWidth: "none" }}
      >
        {visible.map((tab) => {
          const count = badgeCounts?.[tab.key];
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onTabChange(tab.key)}
              className={`relative flex min-h-11 shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 font-mono text-xs uppercase tracking-[0.16em] transition-colors ${
                isActive
                  ? "bg-accent/12 text-accent-on-tint"
                  : "text-muted-foreground hover:bg-elevated hover:text-foreground-secondary"
              }`}
              aria-current={isActive ? "page" : undefined}
            >
              {tab.label}
              {count && count > 0 ? (
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[11px] font-bold ${
                    tab.key === "actions"
                      ? "bg-warning/20 text-warning"
                      : "bg-accent/20 text-accent-on-tint"
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
