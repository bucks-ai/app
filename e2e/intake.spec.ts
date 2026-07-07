// Core intake-to-blueprint flow for the product's product core gate: fill
// the founder intake, generate a blueprint (via E2E_FAKE_AI so the run is
// deterministic and free), confirm it renders and auto-saves, then confirm
// the saved business shows up on the dashboard. Failure here must fail CI.
//
// Requires TEST_USER_EMAIL / TEST_USER_PASSWORD pointing at the user seeded
// by `npm run seed:e2e` (see scripts/seed-e2e.ts), and E2E_FAKE_AI=true so
// /api/generate-blueprint returns the deterministic fixture from
// src/lib/e2e-fake-ai.ts instead of calling a real AI provider.

import { randomUUID } from "node:crypto";
import { test, expect } from "@playwright/test";

const TEST_USER_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_USER_PASSWORD = process.env.TEST_USER_PASSWORD;

test.describe("intake to blueprint", () => {
  test.skip(
    !TEST_USER_EMAIL || !TEST_USER_PASSWORD,
    "TEST_USER_EMAIL / TEST_USER_PASSWORD not set — run `npm run seed:e2e` and set them first."
  );

  test.skip(
    process.env.E2E_FAKE_AI !== "true",
    "E2E_FAKE_AI must be set to true so blueprint generation is deterministic and does not call a real AI provider."
  );

  test("submits the intake form, renders the generated blueprint, saves it, and it shows up on the dashboard", async ({
    page,
  }) => {
    // Longer than the Playwright default: this journey crosses four pages
    // (login, dashboard, intake, blueprint) plus a generate + save round trip.
    test.setTimeout(60000);

    const ideaName = `E2E Blueprint Co ${randomUUID()}`;

    await page.goto("/login");
    await page.locator('input[name="email"]').fill(TEST_USER_EMAIL!);
    await page.locator('input[name="password"]').fill(TEST_USER_PASSWORD!);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.goto("/intake");

    // Step 1: Idea Basics
    await page.locator('input[name="ideaName"]').fill(ideaName);
    await page
      .locator('input[name="oneLineIdea"]')
      .fill("A self-driving operator for AI/software startups.");
    await page.getByRole("button", { name: /continue/i }).click();

    // Step 2: Business Goal
    await page
      .locator('textarea[name="primaryGoal"]')
      .fill("Validate demand with 5 paying design partners in 8 weeks.");
    await page.getByRole("button", { name: /continue/i }).click();

    // Step 3: Execution Limits
    await page.locator('input[name="budget"]').fill("$8,000 to first launch");
    await page.locator('input[name="timeline"]').fill("Launch in 6 weeks");
    await page.getByRole("button", { name: /continue/i }).click();

    // Step 4: Boundaries — no required fields, go straight to generation.
    await page.getByRole("button", { name: /generate blueprint/i }).click();

    // The generated blueprint renders with its key sections.
    await expect(
      page.getByRole("heading", { name: `${ideaName} Mission Control` })
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Business / Product")).toBeVisible();
    await expect(page.getByText("Suggested Stack")).toBeVisible();
    await expect(page.getByText("GTM / Marketing / Sales")).toBeVisible();
    await expect(page.getByText("Controls / Permissions")).toBeVisible();

    // It auto-saves right after generation.
    await expect(page.getByText(/saved to mission control/i)).toBeVisible({
      timeout: 15000,
    });

    // It shows up on the dashboard.
    await page.goto("/dashboard");
    await expect(
      page.getByRole("heading", { name: ideaName })
    ).toBeVisible();
  });
});
