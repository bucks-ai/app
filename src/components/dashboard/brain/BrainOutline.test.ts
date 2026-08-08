// The mobile outline is the whole navigation below lg, so it has to reach
// every destination the canvas reaches — and none of them can be a dead link.

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BrainOutline } from "@/components/dashboard/brain/BrainOutline";
import {
  LOBES,
  buildBrainNodes,
  type BrainBusiness,
} from "@/components/dashboard/brain/brain-model";

const BUSINESSES: BrainBusiness[] = [
  {
    id: "acme",
    name: "Acme Analytics",
    detail: "B2B SaaS",
    tone: "accent",
    approvals: 2,
    blockers: 0,
    live: true,
  },
];

function render(businesses: BrainBusiness[]) {
  return renderToStaticMarkup(
    React.createElement(BrainOutline, {
      businesses,
      nodes: buildBrainNodes(businesses),
    })
  );
}

function hrefs(html: string) {
  return [...html.matchAll(/href="([^"]*)"/g)].map((match) => match[1]);
}

describe("BrainOutline", () => {
  it("renders every lobe for a business", () => {
    const html = render(BUSINESSES);
    for (const lobe of LOBES) {
      expect(html, `missing lobe ${lobe.key}`).toContain(`>${lobe.label}<`);
    }
  });

  it("renders every leaf the model defines", () => {
    const html = render(BUSINESSES);
    const leafTotal = LOBES.reduce((sum, lobe) => sum + lobe.leaves.length, 0);
    // Every leaf, plus one link per leafless lobe, plus the two action links.
    const leaflessLobes = LOBES.filter((lobe) => lobe.leaves.length === 0).length;
    expect(hrefs(html)).toHaveLength(leafTotal + leaflessLobes + 2);
  });

  it("never emits an empty or placeholder href", () => {
    for (const href of hrefs(render(BUSINESSES))) {
      expect(href.trim()).not.toBe("");
      expect(href).not.toBe("#");
    }
  });

  it("points every workspace link at the business it belongs to", () => {
    const workspaceLinks = hrefs(render(BUSINESSES)).filter((href) =>
      href.startsWith("/dashboard/businesses/")
    );
    expect(workspaceLinks.length).toBeGreaterThan(0);
    for (const href of workspaceLinks) {
      expect(href).toContain("/dashboard/businesses/acme?tab=");
    }
  });

  it("explains itself rather than rendering blank when there are no businesses", () => {
    const html = render([]);
    expect(html).toContain("No businesses yet");
  });
});
