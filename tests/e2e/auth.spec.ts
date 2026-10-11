import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { alertWithText, loginThroughForm, signInAs } from "./support/session";

test.describe("sign in", () => {
  test("asks for both fields before calling the API", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(alertWithText(page, "Enter your email and password.")).toBeVisible();
  });

  test("shows the API's message for a wrong password", async ({ page }) => {
    await loginThroughForm(page, fixtures().users.patientEmpty.email, "not-the-password");
    await expect(alertWithText(page, "Invalid email or password.")).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  for (const [key, path] of [
    ["patient", /\/dashboard\/patient$/],
    ["doctor", /\/dashboard\/doctor$/],
    ["admin", /\/admin$/],
  ] as const) {
    test(`a ${key} lands on their own dashboard`, async ({ page }) => {
      await loginThroughForm(page, fixtures().users[key].email);
      await expect(page).toHaveURL(path);
    });
  }
});

test.describe("protected pages", () => {
  test("without a session they send you to sign in", async ({ page }) => {
    for (const path of ["/dashboard/patient", "/dashboard/doctor", "/admin"]) {
      await page.goto(path);
      await expect(page).toHaveURL(/\/login$/);
    }
  });

  test("the wrong role is sent to its own dashboard", async ({ page }) => {
    await signInAs(page, fixtures().users.patient);
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/dashboard\/patient$/);
    await page.goto("/dashboard/doctor");
    await expect(page).toHaveURL(/\/dashboard\/patient$/);
  });

  test("a revoked or invalid token signs you out", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("nora_medlink_token", "not-a-valid-token");
      localStorage.setItem("nora_medlink_user", JSON.stringify({ id: 1, role: "patient", full_name: "Someone" }));
    });
    await page.goto("/dashboard/patient");
    await expect(page).toHaveURL(/\/login$/);
    expect(await page.evaluate(() => localStorage.getItem("nora_medlink_token"))).toBeNull();
  });
});

test.describe("old URLs and unknown pages", () => {
  test("/dashboard and /doctor-dashboard redirect to the new dashboards", async ({ request }) => {
    for (const [from, to] of [
      ["/dashboard", "/dashboard/patient"],
      ["/doctor-dashboard", "/dashboard/doctor"],
    ]) {
      const response = await request.get(from, { maxRedirects: 0 });
      expect(response.status()).toBe(307);
      expect(response.headers().location).toBe(to);
    }
  });

  test("an unknown page shows the not-found page", async ({ page }) => {
    const response = await page.goto("/no-such-page");
    expect(response?.status()).toBe(404);
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  });
});
