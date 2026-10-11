import { expect, test } from "@playwright/test";

import { expectNoHorizontalScroll } from "./support/session";

test.describe("landing page", () => {
  test("shows the hero, the 3D scene and working calls to action", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "Your medical reports, organised and explained." })).toBeVisible();
    await expect(page.locator("canvas").first()).toBeVisible();

    await page.getByRole("link", { name: "Create your account" }).click();
    await expect(page).toHaveURL(/\/signup\?role=patient$/);
    await expect(page.getByRole("radio", { name: /Patient/ })).toBeChecked();
  });

  test("section links scroll to their sections", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Safety" }).click();
    await expect(page).toHaveURL(/#safety$/);
    await expect(page.locator("#safety")).toBeInViewport();
  });

  test("content is visible with reduced motion", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await page.keyboard.press("End");
    await expect(page.locator("footer")).toBeVisible();
    await expect(page.locator("[data-reveal='hidden']")).toHaveCount(0);
  });
});

test.describe("phone width @mobile", () => {
  for (const path of ["/", "/login", "/signup", "/doctors", "/about", "/summarize", "/emergency"]) {
    test(`${path} has no horizontal scroll`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expectNoHorizontalScroll(page);
    });
  }
});
