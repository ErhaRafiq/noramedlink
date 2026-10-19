import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { alertWithText } from "./support/session";

test.describe("sign up", () => {
  test("shows field errors and role-specific fields", async ({ page }) => {
    await page.goto("/signup");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText("Enter your full name.")).toBeVisible();
    await expect(page.getByText("Use 13 digits, e.g. 12345-1234567-1.")).toBeVisible();

    await page.getByLabel("Password", { exact: true }).fill("long-enough-1");
    await page.getByLabel("Confirm password").fill("something-else");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText("Passwords do not match.")).toBeVisible();

    await page.getByText("Doctor", { exact: true }).click();
    await expect(page.getByLabel("PMDC/PMC registration number")).toBeVisible();
    await expect(page.getByLabel("CNIC number")).toHaveCount(0);
    await expect(page.getByText("An administrator checks your registration")).toBeVisible();

    await page.getByText("Admin", { exact: true }).click();
    await expect(page.getByLabel("Admin invite code")).toBeVisible();
  });

  test("a new patient account opens the patient dashboard", async ({ page }) => {
    const { run } = fixtures();
    const email = `phase0-test-e2e-signup-${run}@example.com`;
    await page.goto("/signup?role=patient");
    await page.getByLabel("Full name").fill(`phase0-test-e2e signup ${run}`);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Phone number").fill("0300 7654321");
    await page.getByLabel("Password", { exact: true }).fill("E2e-signup-pass-1");
    await page.getByLabel("Confirm password").fill("E2e-signup-pass-1");
    await page.getByLabel("CNIC number").fill("12345-1234567-1");
    await page.getByLabel("Date of birth").fill("1995-05-20");
    await page.getByLabel("Gender").selectOption("female");
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page).toHaveURL(/\/dashboard\/patient$/, { timeout: 30_000 });
    await expect(page.getByText("No reports uploaded yet.")).toBeVisible();
  });

  test("an email that is already registered is refused", async ({ page }) => {
    await page.goto("/signup?role=doctor");
    await page.getByLabel("Full name").fill("phase0-test-e2e duplicate");
    await page.getByLabel("Email").fill(fixtures().users.doctor.email);
    await page.getByLabel("Phone number").fill("0300 1112223");
    await page.getByLabel("Password", { exact: true }).fill("E2e-signup-pass-1");
    await page.getByLabel("Confirm password").fill("E2e-signup-pass-1");
    await page.getByLabel("PMDC/PMC registration number").fill("PMC 12345-P");
    await page.getByLabel("Specialization").fill("Cardiology");
    await page.getByLabel("Hospital or clinic").fill("Test Hospital");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(alertWithText(page, "Email already registered")).toBeVisible();
    await expect(page).toHaveURL(/\/signup/);
  });

  test("a PMDC number in any of the register's forms passes the form check before any request is sent", async ({ page }) => {
    let signupCalls = 0;
    await page.route("**/api/auth/signup", (route) => {
      signupCalls += 1;
      return route.abort();
    });
    await page.goto("/signup?role=doctor");
    const number = page.getByLabel("PMDC/PMC registration number");
    const refused = page.getByText("That number is not in a recognised form.");
    for (const bad of ["1815-K", "12345", "1815-AJKK", "P-12345"]) {
      await number.fill(bad);
      await page.getByRole("button", { name: "Create account" }).click();
      await expect(refused).toBeVisible();
    }
    expect(signupCalls).toBe(0);

    for (const good of ["1815-AJK", "12345-P", "100-S", "2000-b", "PMDC 1815 ajk"]) {
      await number.fill(good);
      await page.getByRole("button", { name: "Create account" }).click();
      await expect(refused).toHaveCount(0);
    }
  });
});
