import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { signInAs } from "./support/session";

test.describe("signed-in and signed-out visitors", () => {
  test("someone already signed in who opens sign in or sign up goes to their own dashboard", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.patient);
    await page.goto("/login");
    await expect(page).toHaveURL(/\/dashboard\/patient/);
    await page.goto("/signup");
    await expect(page).toHaveURL(/\/dashboard\/patient/);
    await page.goto("/forgot-password");
    await expect(page).toHaveURL(/\/dashboard\/patient/);
  });

  test("a doctor who opens sign in goes to the doctor dashboard", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.doctor);
    await page.goto("/login");
    await expect(page).toHaveURL(/\/dashboard\/doctor/);
  });

  test("public pages look the same signed in: no profile, no dashboard link", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.patient);
    for (const path of ["/", "/about"]) {
      await page.goto(path);
      const nav = page.getByRole("navigation", { name: "Main" });
      await expect(nav.getByRole("link", { name: "Get started" })).toBeVisible();
      await expect(nav.getByRole("link", { name: "My profile" })).toHaveCount(0);
      await expect(nav.getByRole("link", { name: /dashboard/i })).toHaveCount(0);
    }
  });

  test("a profile left in the browser after the session ended is cleared and nothing looks signed in", async ({ page }) => {
    await page.addInitScript(() =>
      localStorage.setItem("nora_medlink_user", JSON.stringify({ id: 1, role: "patient", full_name: "Old Session", email: "old@example.com" })),
    );
    await page.goto("/doctors");
    await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Get started" })).toBeVisible();
    await expect.poll(() => page.evaluate(() => localStorage.getItem("nora_medlink_user"))).toBeNull();
  });

  test("a signed-in page without a session goes to sign in and returns after signing in", async ({ page }) => {
    const { users, password } = fixtures();
    await page.goto("/profile");
    await expect(page).toHaveURL(/\/login\?next=%2Fprofile/);
    await page.getByLabel("Email").fill(users.patient.email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/profile$/);
  });

  test("an outside address in ?next= is ignored", async ({ page }) => {
    const { users, password } = fixtures();
    await page.goto("/login?next=//evil.example.com");
    await page.getByLabel("Email").fill(users.patient.email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/dashboard\/patient/);
  });

  test("the session-ended notice shows on the sign in page", async ({ page }) => {
    await page.goto("/login?expired=1");
    await expect(page.getByText("Your session ended. Please sign in again.")).toBeVisible();
  });

  test("signing out in one tab signs out the other @mobile", async ({ page, context }) => {
    const { users } = fixtures();
    await signInAs(page, users.patient);
    await page.goto("/profile");
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    const other = await context.newPage();
    await other.goto("/about");
    await other.evaluate(() => localStorage.removeItem("nora_medlink_user"));
    await expect(page).toHaveURL(/\/login/);
  });
});
