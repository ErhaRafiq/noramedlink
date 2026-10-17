import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { alertWithText, expectNoHorizontalScroll, signInAs } from "./support/session";

// The sign-in, forgot-password and resend calls are limited per client IP; this file is its own client.
test.use({ extraHTTPHeaders: { "x-forwarded-for": "198.51.100.42" } });

test.describe("forgot password", () => {
  test("the sign-in page links to it", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("link", { name: "Forgot your password?" }).click();
    await expect(page).toHaveURL(/\/forgot-password$/);
    await expect(page.getByRole("heading", { name: "Reset your password" }).first()).toBeVisible();
  });

  test("it asks for a valid address, then gives the same answer for any address and asks for the code", async ({ page }) => {
    await page.goto("/forgot-password");
    await page.getByRole("button", { name: "Send me a code" }).click();
    await expect(page.getByText("Enter the email address of your account.")).toBeVisible();

    // An address nobody has registered: the page cannot tell, and says the same as for a real one.
    await page.getByLabel("Email").fill(`phase0-test-e2e-nobody-${Date.now()}@example.com`);
    await page.getByRole("button", { name: "Send me a code" }).click();
    await expect(page.getByText("If that email has an account, we sent a 6-digit code to it.")).toBeVisible();
    await expect(page.getByLabel("6-digit code")).toBeVisible();
    await expect(page.getByRole("button", { name: /Send a new code in \d+ s/ })).toBeDisabled(); // one a minute
  });

  test("the code step checks the form, and a wrong code is refused in plain words", async ({ page }) => {
    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill(fixtures().users.patientEmpty.email);
    await page.getByRole("button", { name: "Send me a code" }).click();
    await expect(page.getByLabel("6-digit code")).toBeVisible();

    await page.getByRole("button", { name: "Change my password" }).click();
    await expect(page.getByText("Enter the 6 digits from the email.")).toBeVisible();
    await expect(page.getByText("Use at least 8 characters.")).toBeVisible();

    await page.getByLabel("6-digit code").fill("12ab34"); // letters are not accepted into the box
    await expect(page.getByLabel("6-digit code")).toHaveValue("1234");
    await page.getByLabel("6-digit code").fill("000000");
    await page.getByLabel("New password", { exact: true }).fill("Another-pass-1");
    await page.getByLabel("Confirm new password").fill("Different-pass-1");
    await page.getByRole("button", { name: "Change my password" }).click();
    await expect(page.getByText("Passwords do not match.")).toBeVisible();

    await page.getByLabel("Confirm new password").fill("Another-pass-1");
    await page.getByRole("button", { name: "Change my password" }).click();
    await expect(alertWithText(page, "That code is not right, or it has expired.")).toBeVisible({ timeout: 20_000 });
    await expect(page).toHaveURL(/\/forgot-password$/); // nothing changed, still here
  });

  test("it fits a phone screen at both steps @mobile", async ({ page }) => {
    await page.goto("/forgot-password");
    await expectNoHorizontalScroll(page);
    await page.getByLabel("Email").fill(fixtures().users.patientEmpty.email);
    await page.getByRole("button", { name: "Send me a code" }).click();
    await expect(page.getByLabel("6-digit code")).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});

test.describe("confirming an email address", () => {
  test("a link without a code, or with one that is not valid, says so and offers a way forward", async ({ page }) => {
    await page.goto("/verify-email");
    await expect(page.getByText("This link has no confirmation code.")).toBeVisible();
    await page.goto(`/verify-email?token=${"x".repeat(43)}`);
    await expect(page.getByText("This link did not work")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/already been used or has expired/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Sign in to get a new link" })).toHaveAttribute("href", "/login");
  });

  test("a new account is asked to confirm its email, and cannot ask for another link at once", async ({ page }) => {
    const email = `phase0-test-e2e-confirm-${Date.now()}@example.com`;
    await page.goto("/signup?role=patient");
    await page.getByLabel("Full name").fill("phase0-test-e2e confirm");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Phone number").fill(`0314 ${String(Date.now()).slice(-7)}`);
    await page.getByLabel("Password", { exact: true }).fill("E2e-confirm-pass-1");
    await page.getByLabel("Confirm password").fill("E2e-confirm-pass-1");
    await page.getByLabel("CNIC number").fill("12345-1234567-1");
    await page.getByLabel("Date of birth").fill("1996-04-05");
    await page.getByLabel("Gender").selectOption("female");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/dashboard\/patient$/, { timeout: 30_000 });

    const banner = page.getByRole("status").filter({ hasText: "Confirm your email address" }).or(page.getByText("Confirm your email address").first());
    await expect(banner.first()).toBeVisible();
    await page.getByRole("button", { name: "Send a new link" }).click();
    // The link from sign-up was sent seconds ago: the server says how long to wait.
    await expect(page.getByText(/Please wait \d+ seconds before asking again/)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("button", { name: /Send a new link in \d+ s/ })).toBeDisabled();
  });

  test("a confirmed account sees no banner", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    await expect(page.getByRole("heading", { name: "Welcome back" }).or(page.getByText("Welcome back").first())).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Confirm your email address")).toHaveCount(0);
  });
});

test.describe("reminder emails", () => {
  test("a person switches the 5-minute reminder off and on in their profile", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/profile");
    const account = page.getByRole("region", { name: "Account" }).or(page.locator("section").filter({ hasText: "Email me 5 minutes before an appointment" })).first();
    const box = account.getByRole("checkbox", { name: /Email me 5 minutes before an appointment/ });
    await expect(box).toBeChecked({ timeout: 30_000 });

    await box.uncheck();
    await account.getByRole("button", { name: "Save account" }).click();
    await expect(account.getByText("Your account details were saved.")).toBeVisible({ timeout: 20_000 });
    await page.reload();
    await expect(page.getByRole("checkbox", { name: /Email me 5 minutes before an appointment/ })).not.toBeChecked({ timeout: 30_000 });

    await page.getByRole("checkbox", { name: /Email me 5 minutes before an appointment/ }).check(); // put it back
    await page.getByRole("button", { name: "Save account" }).click();
    await expect(page.getByText("Your account details were saved.")).toBeVisible({ timeout: 20_000 });
  });

  test("the profile page fits a phone screen with the reminder switch @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/profile");
    await expect(page.getByRole("checkbox", { name: /Email me 5 minutes before an appointment/ })).toBeVisible({ timeout: 30_000 });
    await expectNoHorizontalScroll(page);
  });
});
