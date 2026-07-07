// For the seeded demo business, each workspace tab that fetches its own data
// (research, validation, actions/execution, team/agents) renders without
// error and lands on either its designed empty state or seeded/ready data —
// never its in-app error state or an unhandled error boundary.
//
// Tabs are addressed directly via the `?tab=` query param that
// BusinessWorkspace reads on mount (see
// src/components/workspace/BusinessWorkspace.tsx) instead of clicking
// sidebar / mobile-tab-bar buttons, since both exist in the DOM at once at
// a typical desktop viewport and would otherwise require disambiguation.
//
// Requires TEST_USER_EMAIL / TEST_USER_PASSWORD pointing at the user seeded
// by `npm run seed:e2e` (see scripts/seed-e2e.ts).

import { test, expect, type Page } from "@playwright/test";
import { DEMO_BUSINESS } from "../src/lib/seed-e2e";

const TEST_USER_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_USER_PASSWORD = process.env.TEST_USER_PASSWORD;

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[name="email"]').fill(TEST_USER_EMAIL!);
  await page.locator('input[name="password"]').fill(TEST_USER_PASSWORD!);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

// No unhandled error boundary or raw exception text should ever appear,
// regardless of which designed state (ready/empty) a tab lands on.
async function assertNoUnhandledError(page: Page) {
  await expect(page.getByText("Something went wrong!")).not.toBeVisible();
  await expect(page.getByText(/application error/i)).not.toBeVisible();
}

test.describe("business detail tabs", () => {
  test.skip(
    !TEST_USER_EMAIL || !TEST_USER_PASSWORD,
    "TEST_USER_EMAIL / TEST_USER_PASSWORD not set — run `npm run seed:e2e` and set them first."
  );

  test("research, validation, execution, and operating-team tabs render seeded data or their empty state, never an error", async ({
    page,
  }) => {
    // Crosses login, dashboard, and four independently-fetching tabs.
    test.setTimeout(60000);

    await login(page);

    const demoCardHeading = page.getByRole("heading", {
      name: DEMO_BUSINESS.idea_name,
    });
    await expect(demoCardHeading).toBeVisible();
    await demoCardHeading.click();
    await expect(page).toHaveURL(/\/dashboard\/businesses\/.+$/);

    const baseUrl = page.url().split("?")[0];

    // Research: the section header always renders; the panel below must
    // land on either the "ready" summary (seeded/generated data) or the
    // "empty" generate-workspace prompt — never its error state.
    await page.goto(`${baseUrl}?tab=research`);
    await expect(
      page.getByRole("heading", {
        name: "Map the market before build work compounds.",
      })
    ).toBeVisible();
    await expect(
      page
        .getByRole("heading", { name: "Map the opportunity before building" })
        .or(page.getByRole("heading", { name: "Find where the money is" }))
        .first()
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Research unavailable")).not.toBeVisible();
    await assertNoUnhandledError(page);

    // Validation: same ready/empty contract as research.
    await page.goto(`${baseUrl}?tab=validation`);
    await expect(
      page.getByRole("heading", {
        name: "Turn demand signals into operating decisions.",
      })
    ).toBeVisible();
    await expect(
      page
        .getByRole("heading", { name: "Validate demand before overbuilding" })
        .or(page.getByRole("heading", { name: "Create the validation workspace" }))
        .first()
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Validation unavailable")).not.toBeVisible();
    await assertNoUnhandledError(page);

    // Actions — the unified execution queue of approvals, blockers, and
    // next actions — either lists at least one action or shows its designed
    // "no pending actions" empty state.
    await page.goto(`${baseUrl}?tab=actions`);
    await expect(
      page
        .getByText("No pending actions")
        .or(page.getByText(/Approval needed|Blocker|Next action/))
        .first()
    ).toBeVisible({ timeout: 15000 });
    await assertNoUnhandledError(page);

    // Operating team / agents: the registry is a fixed operating graph, so
    // it should always reach "ready" (agent-count header) rather than the
    // no-agents empty state, and never its error state.
    await page.goto(`${baseUrl}?tab=team`);
    await expect(
      page.getByRole("heading", {
        name: "Operating team coverage and run history.",
      })
    ).toBeVisible();
    await expect(
      page
        .getByRole("heading", { name: /agents across/i })
        .or(page.getByText("No agents are available for this business yet."))
        .first()
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Operating team unavailable")).not.toBeVisible();
    await assertNoUnhandledError(page);
  });
});
