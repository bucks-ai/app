// Core auth flows for the login-breaking-PR gate: signup, login, bad
// password, logout. Assertions rely only on Playwright's built-in
// auto-waiting (toHaveURL / toBeVisible retry until timeout) — no manual
// waitForTimeout or sleeps.
//
// Requires TEST_USER_EMAIL / TEST_USER_PASSWORD pointing at the user seeded
// by `npm run seed:e2e` (see scripts/seed-e2e.ts).
//
// This project requires email confirmation before a session is issued
// (verified via GET /auth/v1/settings — mailer_autoconfirm: false), so a bare
// signup does not land on the dashboard by itself. The signup test uses the
// same admin API scripts/seed-e2e.ts relies on to confirm the new user, then
// completes login — this still exercises the real signup form end-to-end and
// verifies the resulting account can reach the dashboard.

import { randomUUID } from "node:crypto";
import { createClient } from "@supabase/supabase-js";
import { test, expect } from "@playwright/test";
import { findUserIdByEmail } from "../src/lib/seed-e2e";

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

test.describe("auth", () => {
  test.skip(
    !TEST_USER_EMAIL || !TEST_USER_PASSWORD,
    "TEST_USER_EMAIL / TEST_USER_PASSWORD not set — run `npm run seed:e2e` and set them first."
  );

  test("signup with a unique email succeeds and lands on the dashboard", async ({
    page,
  }) => {
    const admin = createAdminClient();
    test.skip(
      !admin,
      "SUPABASE_SERVICE_ROLE_KEY not set — required to confirm the new signup on a project with email confirmation enabled."
    );

    // Supabase's public signUp validates that the domain has a real MX
    // record (bucks.ai has none), so the throwaway address needs a domain
    // that does — gmail.com — even though nothing is ever actually delivered.
    const email = `e2e-signup-${randomUUID()}@gmail.com`;
    const password = `Signup-${randomUUID()}!`;
    let userId: string | null = null;

    try {
      await page.goto("/signup");
      await page.locator('input[name="email"]').fill(email);
      await page.locator('input[name="password"]').fill(password);
      await page.locator('input[name="confirmPassword"]').fill(password);
      await page.getByRole("button", { name: /create account/i }).click();

      // signUp's response time depends on Supabase sending the confirmation
      // email, which can take longer than the default assertion timeout.
      await expect(page.getByText(/account created/i)).toBeVisible({
        timeout: 15000,
      });

      userId = await findUserIdByEmail(admin!, email);
      if (!userId) throw new Error(`Signed-up user ${email} was not found via the admin API.`);
      const { error } = await admin!.auth.admin.updateUserById(userId, {
        email_confirm: true,
      });
      if (error) throw new Error(`Failed to confirm signup test user: ${error.message}`);

      await page.goto("/login");
      await page.locator('input[name="email"]').fill(email);
      await page.locator('input[name="password"]').fill(password);
      await page.getByRole("button", { name: /sign in/i }).click();

      await expect(page).toHaveURL(/\/dashboard$/);
      await expect(
        page.getByRole("heading", { name: "Your businesses" })
      ).toBeVisible();
    } finally {
      if (userId) await admin!.auth.admin.deleteUser(userId);
    }
  });

  test("login with the seeded test user succeeds", async ({ page }) => {
    await page.goto("/login");
    await page.locator('input[name="email"]').fill(TEST_USER_EMAIL!);
    await page.locator('input[name="password"]').fill(TEST_USER_PASSWORD!);
    await page.getByRole("button", { name: /sign in/i }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(
      page.getByRole("heading", { name: "Your businesses" })
    ).toBeVisible();
  });

  test("login with a wrong password shows an error and does not navigate", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.locator('input[name="email"]').fill(TEST_USER_EMAIL!);
    await page.locator('input[name="password"]').fill("definitely-wrong-password");
    await page.getByRole("button", { name: /sign in/i }).click();

    await expect(page.getByText(/invalid login credentials/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test("logout returns to login and dashboard no longer shows the account", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.locator('input[name="email"]').fill(TEST_USER_EMAIL!);
    await page.locator('input[name="password"]').fill(TEST_USER_PASSWORD!);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login$/);

    // The dashboard is a protected page: it gates its content on the session
    // server-side rather than doing a client redirect, so a signed-out visit
    // renders the signed-out prompt in place instead of navigating away.
    await page.goto("/dashboard");
    await expect(
      page.getByRole("heading", {
        name: "Sign in to load your saved businesses.",
      })
    ).toBeVisible();
  });
});
