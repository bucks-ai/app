// Tools page permission queue: for the seeded demo business, the permission
// queue renders the two deterministic pending (`approval_requested`) rows
// created by scripts/seed-e2e.ts (see DEMO_PENDING_TOOL_PERMISSIONS in
// src/lib/seed-e2e.ts), approving one updates its state to Approved, and
// rejecting the other updates its state to Rejected — all live against the
// real /api/tool-permissions backend, not the read-only demo preview.
//
// Requires TEST_USER_EMAIL / TEST_USER_PASSWORD pointing at the user seeded
// by `npm run seed:e2e` (see scripts/seed-e2e.ts).

import { test, expect, type Page } from "@playwright/test";
import { DEMO_PENDING_TOOL_PERMISSIONS } from "../src/lib/seed-e2e";

const TEST_USER_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_USER_PASSWORD = process.env.TEST_USER_PASSWORD;

const [firstPending, secondPending] = DEMO_PENDING_TOOL_PERMISSIONS;

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[name="email"]').fill(TEST_USER_EMAIL!);
  await page.locator('input[name="password"]').fill(TEST_USER_PASSWORD!);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

// Scopes to the single permission-queue card for `toolName`. The tool
// registry sections above the queue (Preferred/Extended tools) render their
// own OperatorPanel `<section>` with the same tool name heading, so heading
// text alone is ambiguous — the "Request approval" action button only ever
// renders inside PermissionActionBar on the queue card, and is always
// present there regardless of the permission's current status, so pairing
// it with the heading uniquely and stably identifies the queue card.
function permissionCard(page: Page, toolName: string) {
  return page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: toolName, exact: true }) })
    .filter({ has: page.getByRole("button", { name: "Request approval", exact: true }) });
}

test.describe("tools page permission queue", () => {
  test.skip(
    !TEST_USER_EMAIL || !TEST_USER_PASSWORD,
    "TEST_USER_EMAIL / TEST_USER_PASSWORD not set — run `npm run seed:e2e` and set them first."
  );

  test("renders the seeded pending queue, approves one tool, and denies another", async ({
    page,
  }) => {
    test.setTimeout(60000);

    await login(page);
    await page.goto("/tools");

    await expect(
      page.getByRole("heading", { name: "Tool Setup Queue" })
    ).toBeVisible();

    const firstCard = permissionCard(page, firstPending.tool_name);
    const secondCard = permissionCard(page, secondPending.tool_name);

    await expect(firstCard.getByText("Approval Requested", { exact: true })).toBeVisible();
    await expect(secondCard.getByText("Approval Requested", { exact: true })).toBeVisible();

    // Approve the first pending tool permission.
    await firstCard.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(firstCard.getByText("Approved", { exact: true })).toBeVisible();
    await expect(firstCard.getByText("Approval Requested", { exact: true })).not.toBeVisible();

    // Reject (deny) the second pending tool permission.
    await secondCard.getByRole("button", { name: "Reject", exact: true }).click();
    await expect(secondCard.getByText("Rejected", { exact: true })).toBeVisible();
    await expect(secondCard.getByText("Approval Requested", { exact: true })).not.toBeVisible();

    // Reloading confirms both updates were persisted, not just client state.
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Tool Setup Queue" })
    ).toBeVisible();
    await expect(permissionCard(page, firstPending.tool_name).getByText("Approved", { exact: true })).toBeVisible();
    await expect(permissionCard(page, secondPending.tool_name).getByText("Rejected", { exact: true })).toBeVisible();
  });
});
