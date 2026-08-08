// The brain's node tree, and the camera math that frames a node's children.
//
// Two rules govern this file:
//
// 1. Every leaf resolves to a destination that already renders content. Lobes
//    whose tab has no separately-addressable sections (Overview, Settings)
//    deliberately have no leaves and navigate on click — padding the tree to
//    make all branches three deep is how dead links get built.
// 2. Positions are pure functions of index and count. Nothing random, so a
//    node sits in the same place on every render and across server/client.

export type BrainTone = "accent" | "warning" | "danger" | "running" | "neutral";

export type BrainLevel = 1 | 2 | 3;

/** The node you zoomed into, versus the ones it revealed. */
export type BrainNodeRole = "focus" | "child";

export type BrainNode = {
  id: string;
  level: BrainLevel;
  parentId: string | null;
  label: string;
  detail: string;
  /** World coordinates — one fixed system the camera moves over. */
  x: number;
  y: number;
  r: number;
  tone: BrainTone;
  count?: number;
  /** Drives the pulse. A claim that work is happening, so never set on sample data. */
  live?: boolean;
  /** Terminal nodes navigate. Nodes with children zoom instead. */
  href?: string;
  /** True when this node has children to zoom into. */
  expandable: boolean;
};

export type LobeDef = {
  key: string;
  label: string;
  detail: string;
  tab: string;
  tone: BrainTone;
  /** Empty means "no third level" — the lobe navigates straight to its tab. */
  leaves: { key: string; label: string; detail: string; section?: string }[];
};

/* Lobes mirror the workspace tabs; leaves mirror the panels each tab actually
   renders. Adding a leaf here without a matching panel creates a link that
   scrolls to nothing, so the two lists move together. */
export const LOBES: LobeDef[] = [
  {
    key: "actions",
    label: "Decisions",
    detail: "what needs you",
    tab: "actions",
    tone: "warning",
    // No third level yet: the Actions tab renders one flat list rather than
    // separately-addressable approval / blocker / next-action sections, so
    // there is nothing for a leaf to scroll to. Group that list and these three
    // leaves can come back.
    leaves: [],
  },
  {
    key: "research",
    label: "Research",
    detail: "market map",
    tab: "research",
    tone: "accent",
    leaves: [
      { key: "opportunity", label: "Opportunity", detail: "score", section: "research-opportunity" },
      { key: "segments", label: "Segments", detail: "who buys", section: "research-segments" },
      { key: "budgets", label: "Budgets", detail: "willingness to pay", section: "research-budgets" },
      { key: "competitors", label: "Competitors", detail: "the field", section: "research-competitors" },
      { key: "monetization", label: "Monetization", detail: "revenue models", section: "research-monetization" },
      { key: "distribution", label: "Distribution", detail: "channels", section: "research-distribution" },
      { key: "risks", label: "Risks", detail: "what kills it", section: "research-risks" },
      { key: "hypotheses", label: "Hypotheses", detail: "to test", section: "research-hypotheses" },
      { key: "evidence", label: "Evidence", detail: "sources", section: "research-evidence" },
    ],
  },
  {
    key: "validation",
    label: "Validation",
    detail: "demand signal",
    tab: "validation",
    tone: "accent",
    leaves: [
      { key: "leads", label: "Leads", detail: "pipeline", section: "validation-leads" },
      { key: "personas", label: "Personas", detail: "who we talked to", section: "validation-personas" },
      { key: "hypotheses", label: "Hypotheses", detail: "tracker", section: "validation-hypotheses" },
      { key: "feedback", label: "Feedback", detail: "notes", section: "validation-feedback" },
    ],
  },
  {
    key: "build",
    label: "Build",
    detail: "repo and scaffold",
    tab: "build",
    tone: "accent",
    leaves: [
      { key: "repo", label: "Repository", detail: "GitHub", section: "build-repo" },
      { key: "scaffold", label: "Scaffold", detail: "starter app", section: "build-scaffold" },
    ],
  },
  {
    key: "deploy",
    label: "Deploy",
    detail: "live surface",
    tab: "deploy",
    tone: "accent",
    leaves: [
      { key: "status", label: "Status", detail: "deployment state", section: "deploy-status" },
      { key: "execution", label: "Execution", detail: "build runs", section: "deploy-execution" },
    ],
  },
  {
    key: "tools",
    label: "Tools",
    detail: "permissions",
    tab: "tools",
    tone: "warning",
    leaves: [
      { key: "permissions", label: "Permissions", detail: "control room", section: "tools-permissions" },
      { key: "queue", label: "Queue", detail: "awaiting approval", section: "tools-queue" },
    ],
  },
  {
    key: "team",
    label: "Team",
    detail: "agent roster",
    tab: "team",
    tone: "running",
    leaves: [
      { key: "roster", label: "Roster", detail: "coverage", section: "team-roster" },
      { key: "runs", label: "Run history", detail: "timeline", section: "team-runs" },
    ],
  },
  {
    key: "activity",
    label: "Activity",
    detail: "event log",
    tab: "activity",
    tone: "neutral",
    leaves: [],
  },
  {
    key: "overview",
    label: "Overview",
    detail: "snapshot",
    tab: "overview",
    tone: "neutral",
    leaves: [],
  },
];

export type BrainBusiness = {
  id: string;
  name: string;
  detail: string;
  tone: BrainTone;
  approvals: number;
  blockers: number;
  live: boolean;
};

/* World-space constants. The brain silhouette is authored against this box, so
   node placement and the outline path share one coordinate system.

   The world is portrait and generous: a brain seen from above is taller than
   it is wide, and the cortex has to be large enough that a business node plus
   its ring of lobes still sits inside the outline. Lobes floating outside the
   boundary break the one metaphor the page is built on. */
export const WORLD_W = 1900;
export const WORLD_H = 2200;
export const CORE = { x: WORLD_W / 2, y: WORLD_H / 2 };

/** Cortex semi-axes. Portrait: front-to-back is the long dimension. */
export const CORTEX_RX = 760;
export const CORTEX_RY = 910;

/* Bounding box of the drawn cortex. Level 1 frames *this*, not the node
   cluster — fitting only the business nodes leaves the silhouette they sit
   inside hanging off every edge of the viewport. */
export const CORTEX_BOUNDS = {
  minX: CORE.x - CORTEX_RX - 20,
  maxX: CORE.x + CORTEX_RX + 20,
  minY: CORE.y - CORTEX_RY - 20,
  maxY: CORE.y + CORTEX_RY + 20,
};

/* Ring radii must shrink with depth, or drilling in zooms *out*: a nine-leaf
   lobe cluster on a small ring is physically wider than the nine-lobe cluster
   that contains it, and the camera dutifully pulls back to fit it. Each level's
   cluster is sized to be comfortably smaller than its parent's.

   BUSINESS_RING + LOBE_RING must also stay under CORTEX_RX, or a business's
   lobes render outside the silhouette that is supposed to contain them. */
const BUSINESS_RING = 380;
const LOBE_RING = 300;
const LEAF_RING = 150;

/* Distributes n points over an arc centred on `from`. One item sits dead
   centre rather than off to one side, which is what a naive i/n split does. */
function ring(
  cx: number,
  cy: number,
  radius: number,
  index: number,
  total: number,
  rotation = 0,
  /* Squashed vertically so clusters read as brain lobes rather than clock
     faces. Leaves use a rounder ring — labels are wider than they are tall, so
     a squashed ring collides them top and bottom. */
  squash = 0.72
) {
  const angle = total === 1 ? rotation : rotation + (index / total) * Math.PI * 2;
  return {
    x: cx + Math.cos(angle) * radius,
    y: cy + Math.sin(angle) * radius * squash,
  };
}

/* Labels are far wider than the node discs, so a fixed ring collides them as
   soon as a lobe has more than about five leaves. Research has nine. */
function leafRing(count: number) {
  // Spacing must clear the node diameter, or nine leaves overlap each other.
  return Math.max(LEAF_RING, count * 27);
}

export function buildBrainNodes(businesses: BrainBusiness[]): BrainNode[] {
  const nodes: BrainNode[] = [];

  businesses.forEach((business, businessIndex) => {
    const pos = ring(
      CORE.x,
      CORE.y,
      businesses.length === 1 ? 0 : BUSINESS_RING,
      businessIndex,
      businesses.length,
      -Math.PI / 2
    );

    nodes.push({
      id: business.id,
      level: 1,
      parentId: null,
      label: business.name,
      detail: business.detail,
      x: pos.x,
      y: pos.y,
      r: 138,
      tone: business.tone,
      count: business.approvals,
      live: business.live,
      expandable: true,
    });

    LOBES.forEach((lobe, lobeIndex) => {
      const lobePos = ring(
        pos.x,
        pos.y,
        LOBE_RING,
        lobeIndex,
        LOBES.length,
        -Math.PI / 2
      );
      const lobeId = `${business.id}:${lobe.key}`;
      const count =
        lobe.key === "actions"
          ? business.approvals + business.blockers
          : undefined;

      nodes.push({
        id: lobeId,
        level: 2,
        parentId: business.id,
        label: lobe.label,
        detail: lobe.detail,
        x: lobePos.x,
        y: lobePos.y,
        r: 95,
        tone: lobe.tone,
        count,
        live: business.live && lobe.key === "actions" && count ? count > 0 : false,
        expandable: lobe.leaves.length > 0,
        // A lobe with no third level is itself the destination.
        href:
          lobe.leaves.length === 0
            ? `/dashboard/businesses/${business.id}?tab=${lobe.tab}`
            : undefined,
      });

      lobe.leaves.forEach((leaf, leafIndex) => {
        const leafPos = ring(
          lobePos.x,
          lobePos.y,
          leafRing(lobe.leaves.length),
          leafIndex,
          lobe.leaves.length,
          -Math.PI / 2,
          0.88
        );

        nodes.push({
          id: `${lobeId}:${leaf.key}`,
          level: 3,
          parentId: lobeId,
          label: leaf.label,
          detail: leaf.detail,
          x: leafPos.x,
          y: leafPos.y,
          r: 75,
          tone: lobe.tone,
          expandable: false,
          href: `/dashboard/businesses/${business.id}?tab=${lobe.tab}${
            leaf.section ? `&section=${leaf.section}` : ""
          }`,
        });
      });
    });
  });

  return nodes;
}

export type Camera = { x: number; y: number; k: number };

/**
 * Frames a node and its children. Returns world-space centre plus the scale
 * that fits the cluster into `viewport`, so the same call works for the whole
 * brain (focus === null) and for a single lobe.
 */
export function cameraFor(
  nodes: BrainNode[],
  focusId: string | null,
  viewport: { w: number; h: number }
): Camera {
  const focus = focusId ? nodes.find((node) => node.id === focusId) ?? null : null;

  let minX: number;
  let maxX: number;
  let minY: number;
  let maxY: number;
  let pad: number;

  if (!focus) {
    // Whole brain: frame the silhouette so the cortex reads as one shape.
    ({ minX, maxX, minY, maxY } = CORTEX_BOUNDS);
    pad = 40;
  } else {
    const members = [focus, ...nodes.filter((node) => node.parentId === focus.id)];
    minX = Infinity;
    maxX = -Infinity;
    minY = Infinity;
    maxY = -Infinity;

    for (const node of members) {
      minX = Math.min(minX, node.x - node.r);
      maxX = Math.max(maxX, node.x + node.r);
      minY = Math.min(minY, node.y - node.r);
      maxY = Math.max(maxY, node.y + node.r);
    }

    // Labels sit outside the node radius, so bounds get padding before fit.
    pad = 90;
  }

  const width = maxX - minX + pad * 2;
  const height = maxY - minY + pad * 2;
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;

  const k = Math.min(3, Math.max(0.3, Math.min(viewport.w / width, viewport.h / height)));

  return {
    k,
    x: viewport.w / 2 - cx * k,
    y: viewport.h / 2 - cy * k,
  };
}

/** Ancestor chain, root first — the breadcrumb and the back path. */
export function pathTo(nodes: BrainNode[], id: string | null): BrainNode[] {
  const chain: BrainNode[] = [];
  let cursor = id ? nodes.find((node) => node.id === id) ?? null : null;

  while (cursor) {
    chain.unshift(cursor);
    cursor = cursor.parentId
      ? nodes.find((node) => node.id === cursor?.parentId) ?? null
      : null;
  }

  return chain;
}

/**
 * What the camera shows at a given focus: the focused node and its children.
 *
 * Siblings used to render as dimmed "context" so a zoom would not read as the
 * rest of the brain being deleted. They are gone, because they never actually
 * delivered that: `cameraFor` frames the focus and its children only, so
 * siblings sat wholly outside the viewport at every depth — while still being
 * in the DOM and in the tab order. That is two invisible tab stops with no
 * focus indicator (WCAG 2.4.7). Orientation is the breadcrumb's job instead.
 */
export function visibleNodes(
  nodes: BrainNode[],
  focusId: string | null
): { node: BrainNode; role: BrainNodeRole }[] {
  if (!focusId) {
    return nodes
      .filter((node) => node.level === 1)
      .map((node) => ({ node, role: "child" as const }));
  }

  const focus = nodes.find((node) => node.id === focusId);
  if (!focus) return [];

  const out: { node: BrainNode; role: BrainNodeRole }[] = [
    { node: focus, role: "focus" },
  ];

  for (const node of nodes) {
    if (node.parentId === focus.id) {
      out.push({ node, role: "child" });
    }
  }

  return out;
}
