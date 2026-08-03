import { test, expect } from "@playwright/test";

test("home page renders", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: /execution-ready MVP workspace/i })
  ).toBeVisible();
  await expect(
    page.getByRole("main").getByRole("link", { name: "Start building" }).first()
  ).toBeVisible();
});
