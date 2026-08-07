// The Actions tab used to render every item as a card with hover styling and
// no control on it — the founder could click and nothing happened. These tests
// pin the controls: an approval backed by a human_required_actions row gets
// Approve/Dismiss, and a blocker or next action carrying an href gets a way to
// reach it.

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn(), replace: vi.fn() }),
}));

import { ActionsTab } from "@/components/workspace/tabs/ActionsTab";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";

const BUSINESS_ID = "business-1";

function makeBusiness(
  overrides: Partial<DashboardBusiness> = {}
): DashboardBusiness {
  return {
    id: BUSINESS_ID,
    name: "Acme Analytics",
    oneLineIdea: "Analytics for small teams.",
    sourceLabel: "Saved build record",
    businessType: "SaaS",
    status: "Building",
    statusVariant: "neutral",
    goal: "Ship the MVP",
    created: "Aug 6, 2026",
    overview: "Saved business project.",
    blueprintSummary: "Summary",
    nextActions: [],
    humanActions: [],
    humanActionItems: [],
    activity: [],
    permissions: [],
    ...overrides,
  } as DashboardBusiness;
}

function makeExecutionStatus(
  overrides: Partial<BusinessExecutionStatus> = {}
): BusinessExecutionStatus {
  return {
    businessId: BUSINESS_ID,
    currentPhase: "build",
    health: "on_track",
    progressPercent: 40,
    milestones: [],
    blockers: [],
    nextActions: [],
    assets: [],
    timeline: [],
    ...overrides,
  } as BusinessExecutionStatus;
}

describe("ActionsTab", () => {
  it("gives a database-backed approval real Approve and Dismiss buttons", () => {
    const html = renderToStaticMarkup(
      React.createElement(ActionsTab, {
        business: makeBusiness({
          humanActionItems: [
            {
              id: "action-1",
              title: "Register the business",
              business: "Acme Analytics",
              reason: "Legal operation",
              status: "Pending",
            },
          ],
        }),
      })
    );

    expect(html).toContain("Register the business");
    expect(html).toContain(">Approve<");
    expect(html).toContain(">Dismiss<");
  });

  it("renders no decision buttons for an approval with no row to decide against", () => {
    const html = renderToStaticMarkup(
      React.createElement(ActionsTab, {
        business: makeBusiness({
          humanActionItems: undefined,
          humanActions: ["Approve first outreach segment"],
        }),
      })
    );

    expect(html).toContain("Approve first outreach segment");
    expect(html).not.toContain(">Dismiss<");
  });

  it("turns a blocker's legacy section anchor into a tab control", () => {
    const html = renderToStaticMarkup(
      React.createElement(ActionsTab, {
        business: makeBusiness(),
        executionStatus: makeExecutionStatus({
          blockers: [
            {
              id: "tool-approval",
              title: "GitHub needs approval",
              description: "Approve GitHub before the repo can be created.",
              severity: "blocked",
              owner: "founder",
              href: `/dashboard/businesses/${BUSINESS_ID}#tools`,
            },
          ],
        }),
        onTabChange: () => {},
      })
    );

    expect(html).toContain("GitHub needs approval");
    expect(html).toContain("Open Tools");
  });

  it("links a next action that points outside the workspace", () => {
    const html = renderToStaticMarkup(
      React.createElement(ActionsTab, {
        business: makeBusiness(),
        executionStatus: makeExecutionStatus({
          nextActions: [
            {
              id: "generate_blueprint",
              title: "Generate blueprint",
              description: "Create the launch blueprint.",
              actor: "founder",
              priority: "high",
              href: "/intake",
            },
          ],
        }),
        onTabChange: () => {},
      })
    );

    expect(html).toContain('href="/intake"');
  });

  it("leaves an action with no href and no row without a dead control", () => {
    const html = renderToStaticMarkup(
      React.createElement(ActionsTab, {
        business: makeBusiness(),
        executionStatus: makeExecutionStatus({
          nextActions: [
            {
              id: "wait_for_run",
              title: "Wait for the current run",
              description: "bucks.ai is working on it.",
              actor: "bucks_ai",
              priority: "low",
            },
          ],
        }),
        onTabChange: () => {},
      })
    );

    expect(html).toContain("Wait for the current run");
    expect(html).not.toContain(">Open<");
    expect(html).not.toContain("interactive-surface");
  });
});
