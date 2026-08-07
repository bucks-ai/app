// Execution status hands blockers and next actions an `href` that predates the
// tabbed workspace — mostly `/dashboard/businesses/<id>#some-anchor`. Those
// anchors no longer exist as page sections, so the Actions tab resolves them
// back to the tab that owns that content instead of rendering a dead link.

import type { TabKey } from "@/components/workspace/WorkspaceTabs";

export type ActionTarget =
  | { kind: "tab"; tab: TabKey }
  | { kind: "internal"; href: string }
  | { kind: "external"; href: string };

const ANCHOR_TO_TAB: Record<string, TabKey> = {
  "human-actions": "actions",
  tools: "tools",
  "repository-execution": "build",
  "deployment-execution": "deploy",
  research: "research",
  validation: "validation",
  activity: "activity",
  team: "team",
  settings: "settings",
  overview: "overview",
};

export function resolveActionTarget(
  href: string | null | undefined,
  businessId: string
): ActionTarget | null {
  const trimmed = href?.trim();
  if (!trimmed) return null;

  if (/^https?:\/\//i.test(trimmed)) {
    return { kind: "external", href: trimmed };
  }

  // "//host" is protocol-relative and leaves the app, so it is not an
  // internal link even though it starts with a slash.
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) return null;

  const [path, anchor] = trimmed.split("#");

  // Anchors only map to tabs when they point at this same business.
  if (anchor && path === `/dashboard/businesses/${businessId}`) {
    const tab = ANCHOR_TO_TAB[anchor];
    if (tab) return { kind: "tab", tab };
    return { kind: "tab", tab: "overview" };
  }

  return { kind: "internal", href: trimmed };
}
