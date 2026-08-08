// The brain's contract: every clickable leaf resolves somewhere real, the tree
// is deterministic, and the camera frames what it claims to.

import { describe, expect, it } from "vitest";
import {
  CORE,
  CORTEX_BOUNDS,
  CORTEX_RX,
  CORTEX_RY,
  LOBES,
  buildBrainNodes,
  cameraFor,
  pathTo,
  visibleNodes,
  type BrainBusiness,
} from "@/components/dashboard/brain/brain-model";

const BUSINESSES: BrainBusiness[] = [
  {
    id: "acme",
    name: "Acme Analytics",
    detail: "B2B SaaS",
    tone: "accent",
    approvals: 2,
    blockers: 1,
    live: true,
  },
  {
    id: "clipforge",
    name: "ClipForge AI",
    detail: "Creator Tool",
    tone: "warning",
    approvals: 0,
    blockers: 0,
    live: false,
  },
];

const VIEWPORT = { w: 1440, h: 824 };

describe("buildBrainNodes", () => {
  it("builds one node per business, lobe, and leaf", () => {
    const nodes = buildBrainNodes(BUSINESSES);
    const leafTotal = LOBES.reduce((sum, lobe) => sum + lobe.leaves.length, 0);

    expect(nodes.filter((node) => node.level === 1)).toHaveLength(2);
    expect(nodes.filter((node) => node.level === 2)).toHaveLength(2 * LOBES.length);
    expect(nodes.filter((node) => node.level === 3)).toHaveLength(2 * leafTotal);
  });

  it("is deterministic — the same input yields identical positions", () => {
    expect(buildBrainNodes(BUSINESSES)).toEqual(buildBrainNodes(BUSINESSES));
  });

  it("gives every node a unique id", () => {
    const nodes = buildBrainNodes(BUSINESSES);
    expect(new Set(nodes.map((node) => node.id)).size).toBe(nodes.length);
  });

  it("centres a lone business rather than stranding it on the ring", () => {
    const [only] = buildBrainNodes([BUSINESSES[0]]).filter((node) => node.level === 1);
    expect(only.x).toBe(CORE.x);
    expect(only.y).toBe(CORE.y);
  });

  it("keeps a business and its lobes inside the cortex", () => {
    const nodes = buildBrainNodes(BUSINESSES);
    // A lobe rendered outside the silhouette breaks the one metaphor the page
    // is built on, so the ring radii are constrained against the cortex.
    for (const node of nodes.filter((entry) => entry.level <= 2)) {
      const dx = (node.x - CORE.x) / CORTEX_RX;
      const dy = (node.y - CORE.y) / CORTEX_RY;
      expect(Math.hypot(dx, dy), `${node.id} sits outside the cortex`).toBeLessThan(1);
    }
  });
});

describe("every node either navigates or expands", () => {
  const nodes = buildBrainNodes(BUSINESSES);

  it("leaves all carry an href — no leaf is a dead end", () => {
    const leaves = nodes.filter((node) => node.level === 3);
    expect(leaves.length).toBeGreaterThan(0);
    for (const leaf of leaves) {
      expect(leaf.href, `${leaf.id} has no href`).toBeTruthy();
      expect(leaf.expandable).toBe(false);
    }
  });

  it("a lobe with no leaves navigates instead of zooming into nothing", () => {
    for (const lobe of LOBES) {
      const node = nodes.find((entry) => entry.id === `acme:${lobe.key}`);
      expect(node).toBeDefined();
      if (lobe.leaves.length === 0) {
        expect(node?.href, `${lobe.key} is leafless and must link`).toBeTruthy();
        expect(node?.expandable).toBe(false);
      } else {
        expect(node?.expandable).toBe(true);
      }
    }
  });

  it("never produces a node that neither links nor expands", () => {
    for (const node of nodes) {
      expect(
        Boolean(node.href) || node.expandable,
        `${node.id} is a dead click`
      ).toBe(true);
    }
  });

  it("points leaf hrefs at the tab that owns the section", () => {
    const risks = nodes.find((node) => node.id === "acme:research:risks");
    expect(risks?.href).toBe(
      "/dashboard/businesses/acme?tab=research&section=research-risks"
    );
  });
});

describe("cameraFor", () => {
  const nodes = buildBrainNodes(BUSINESSES);

  it("frames the cortex, not just the nodes, at the top level", () => {
    const camera = cameraFor(nodes, null, VIEWPORT);
    const cx = (CORTEX_BOUNDS.minX + CORTEX_BOUNDS.maxX) / 2;
    // The silhouette's centre lands at the centre of the viewport.
    expect(camera.x + cx * camera.k).toBeCloseTo(VIEWPORT.w / 2, 5);
  });

  it("centres the focused cluster, keeping the focus node near the middle", () => {
    const focus = nodes.find((node) => node.id === "acme:research");
    const camera = cameraFor(nodes, "acme:research", VIEWPORT);

    // The camera centres the cluster's bounds rather than the focus node
    // itself, so an odd leaf count leaves the parent slightly off-centre. It
    // must still land near the middle, not drift to an edge.
    const screenX = camera.x + (focus?.x ?? 0) * camera.k;
    const screenY = camera.y + (focus?.y ?? 0) * camera.k;
    expect(Math.abs(screenX - VIEWPORT.w / 2)).toBeLessThan(30);
    expect(Math.abs(screenY - VIEWPORT.h / 2)).toBeLessThan(30);
  });

  it("zooms in as it descends", () => {
    const top = cameraFor(nodes, null, VIEWPORT);
    const business = cameraFor(nodes, "acme", VIEWPORT);
    const lobe = cameraFor(nodes, "acme:research", VIEWPORT);
    expect(business.k).toBeGreaterThan(top.k);
    expect(lobe.k).toBeGreaterThan(business.k);
  });

  it("falls back to the cortex framing for an unknown focus", () => {
    expect(cameraFor(nodes, "does-not-exist", VIEWPORT)).toEqual(
      cameraFor(nodes, null, VIEWPORT)
    );
  });
});

describe("pathTo", () => {
  const nodes = buildBrainNodes(BUSINESSES);

  it("returns the ancestor chain root-first for the breadcrumb", () => {
    expect(pathTo(nodes, "acme:research:risks").map((node) => node.label)).toEqual([
      "Acme Analytics",
      "Research",
      "Risks",
    ]);
  });

  it("is empty at the top level", () => {
    expect(pathTo(nodes, null)).toEqual([]);
  });
});

describe("visibleNodes", () => {
  const nodes = buildBrainNodes(BUSINESSES);

  it("shows only businesses at the top level", () => {
    const visible = visibleNodes(nodes, null);
    expect(visible).toHaveLength(2);
    expect(visible.every((entry) => entry.node.level === 1)).toBe(true);
  });

  it("shows the focused business and its lobes, and nothing else", () => {
    const visible = visibleNodes(nodes, "acme");
    const roles = visible.map((entry) => entry.role);
    expect(roles.filter((role) => role === "focus")).toHaveLength(1);
    expect(roles.filter((role) => role === "child")).toHaveLength(LOBES.length);
    // The whole set is focus + children: no off-screen siblings left in the
    // DOM to collect invisible tab stops.
    expect(visible).toHaveLength(LOBES.length + 1);
  });

  it("renders only the lobe and its leaves at level 3", () => {
    const visible = visibleNodes(nodes, "acme:research");
    const researchLeaves = LOBES.find((lobe) => lobe.key === "research")?.leaves ?? [];
    expect(visible.filter((entry) => entry.role === "child")).toHaveLength(
      researchLeaves.length
    );
    expect(visible).toHaveLength(researchLeaves.length + 1);
  });

  it("never emits a node that the camera would leave outside the frame", () => {
    for (const focusId of [null, "acme", "acme:research"]) {
      const camera = cameraFor(nodes, focusId, VIEWPORT);
      for (const { node } of visibleNodes(nodes, focusId)) {
        const x = camera.x + node.x * camera.k;
        const y = camera.y + node.y * camera.k;
        expect(x, `${node.id} off-screen horizontally at ${focusId}`).toBeGreaterThan(0);
        expect(x).toBeLessThan(VIEWPORT.w);
        expect(y, `${node.id} off-screen vertically at ${focusId}`).toBeGreaterThan(0);
        expect(y).toBeLessThan(VIEWPORT.h);
      }
    }
  });
});
