// Dashboard flows: the seeded demo business renders as a card and opens the
// business detail page; a brand-new user with no businesses sees the empty
// state. Assertions rely only on Playwright's built-in auto-waiting — no
// manual waitForTimeout or sleeps.
//
// Requires TEST_USER_EMAIL / TEST_USER_PASSWORD pointing at the user seeded
// by `npm run seed:e2e` (see scripts/seed-e2e.ts), plus Supabase service-role
// credentials to create and clean up the throwaway empty-state user.

import { randomUUID } from "node:crypto";
import { createClient } from "@supabase/supabase-js";
import { test, expect } from "@playwright/test";
import { DEMO_BUSINESS } from "../src/lib/seed-e2e";

const TEST_USER_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_USER_PASSWORD = process.env.TEST_USER_PASSWORD;
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

function createAdminClient() {
  if (!SUPABASE_URL || !SERVICE_ROLE_KEY) return null;
  return createClient(SUPABASE_URL, SERVICE_ROLE_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

async function login(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/login");
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test.describe("dashboard", () => {
  test.skip(
    !TEST_USER_EMAIL || !TEST_USER_PASSWORD,
    "TEST_USER_EMAIL / TEST_USER_PASSWORD not set — run `npm run seed:e2e` and set them first."
  );

  test("lists the seeded demo business and opens its detail page", async ({ page }) => {
    await login(page, TEST_USER_EMAIL!, TEST_USER_PASSWORD!);

    await expect(
      page.getByRole("heading", { name: "Your businesses" })
    ).toBeVisible();

    const demoCardHeading = page.getByRole("heading", {
      name: DEMO_BUSINESS.idea_name,
    });
    await expect(demoCardHeading).toBeVisible();

    await demoCardHeading.click();

    await expect(page).toHaveURL(/\/dashboard\/businesses\/.+$/);
    await expect(
      page.getByRole("heading", { level: 1, name: DEMO_BUSINESS.idea_name })
    ).toBeVisible();
  });

  test("shows the empty state for a fresh user with no businesses", async ({ page }) => {
    const admin = createAdminClient();
    test.skip(
      !admin,
      "SUPABASE_SERVICE_ROLE_KEY not set — required to create a throwaway user for the empty-state assertion."
    );

    const email = `e2e-empty-${randomUUID()}@bucks.ai`;
    const password = `Empty-${randomUUID()}!`;
    let userId: string | null = null;

    try {
      const { data, error } = await admin!.auth.admin.createUser({
        email,
        password,
        email_confirm: true,
      });
      if (error || !data.user) {
        throw new Error(`Failed to create throwaway empty-state user: ${error?.message ?? "no user returned"}`);
      }
      userId = data.user.id;

      await login(page, email, password);

      await expect(
        page.getByRole("heading", { name: "Start your first business" })
      ).toBeVisible();
      await expect(
        page.getByRole("heading", { name: DEMO_BUSINESS.idea_name })
      ).not.toBeVisible();
    } finally {
      if (userId) await admin!.auth.admin.deleteUser(userId);
    }
  });
});
