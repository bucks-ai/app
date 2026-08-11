import { test, expect } from "@playwright/test";

test("home page renders", async ({ page }) => {
  await page.goto("/");

  // Landing was redesigned ~2026-08-04 and this spec was not updated with it,
  // leaving App CI red for 13 consecutive runs. These assertions track
  // HomeHero's current h1 and primary CTA — update them WITH any hero rewrite.
  await expect(
    page.getByRole("heading", { name: /mission control for founder-led MVPs/i })
  ).toBeVisible();
  await expect(
    page.getByRole("main").getByRole("link", { name: "Enter the console" }).first()
  ).toBeVisible();
});
