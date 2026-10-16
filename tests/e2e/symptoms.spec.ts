import { expect, test, type Page } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

// The e2e cleanup removes saved checks whose text starts with this marker.
const MARK = "phase0-test-e2e ";

async function check(page: Page, text: string) {
  await page.goto("/symptoms");
  await page.getByLabel("Your symptoms").fill(MARK + text);
  await page.getByRole("button", { name: "Check my symptoms" }).click();
}

test.describe("symptom checker", () => {
  test("a warning sign shows the emergency notice and nothing to book", async ({ page }) => {
    await check(page, "Chest pain, dizziness, shortness of breath");
    const notice = page.getByRole("alert").filter({ hasText: "This may be an emergency" });
    await expect(notice).toBeVisible({ timeout: 20_000 });
    await expect(notice).toContainText("Call 1122 or go to the nearest emergency department.");
    await expect(notice).toContainText("Chest pain or pressure");
    await expect(page.getByRole("button", { name: "Book appointment" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Which doctor should I see?" })).toBeVisible();
    await notice.getByRole("button", { name: "Start again" }).click();
    await expect(page.getByLabel("Your symptoms")).toHaveValue("");
  });

  test("a rash points to dermatology, and no doctor is invented", async ({ page }) => {
    await check(page, "itchy rash on my arm for a week");
    const result = page.getByRole("article", { name: "Dermatologist" });
    await expect(result).toBeVisible({ timeout: 20_000 });
    await expect(result).toContainText("itchy rash");
    await expect(result).toContainText("No verified dermatologist is listed yet.");
    await expect(page.getByText("Advisory only").first()).toBeVisible();
  });

  test("fever lists the verified general physician, and a visitor is asked to sign in to book", async ({ page }) => {
    const { users } = fixtures();
    await check(page, "fever and sore throat for 2 days");
    const result = page.getByRole("article", { name: "General Physician" });
    await expect(result).toBeVisible({ timeout: 20_000 });
    await expect(result.getByRole("heading", { name: users.doctor.fullName })).toBeVisible();
    await expect(result.getByRole("heading", { name: users.doctorUnreviewed.fullName })).toHaveCount(0); // pending: never listed
    await result.getByRole("article").filter({ hasText: users.doctor.fullName }).getByRole("button", { name: "Book appointment" }).click();
    await expect(page.getByText("Please sign in as a patient to book an appointment.")).toBeVisible();
  });

  test("a signed-in patient can open the booking dialog from a result", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.patientEmpty);
    await check(page, "fever and sore throat");
    const result = page.getByRole("article", { name: "General Physician" });
    await result.getByRole("article").filter({ hasText: users.doctor.fullName }).getByRole("button", { name: "Book appointment" }).click();
    await expect(page.getByRole("dialog").getByRole("heading", { name: `Book ${users.doctor.fullName}` })).toBeVisible();
  });

  test("the button waits for a few words", async ({ page }) => {
    await page.goto("/symptoms");
    const button = page.getByRole("button", { name: "Check my symptoms" });
    await expect(button).toBeDisabled();
    await page.getByRole("button", { name: "Fever and sore throat for 2 days" }).click();
    await expect(page.getByLabel("Your symptoms")).toHaveValue("Fever and sore throat for 2 days");
    await expect(button).toBeEnabled();
  });

  test("the page and its emergency result fit a phone screen @mobile", async ({ page }) => {
    await check(page, "chest pain");
    await expect(page.getByRole("alert").filter({ hasText: "This may be an emergency" })).toBeVisible({ timeout: 20_000 });
    await expectNoHorizontalScroll(page);
  });

  test("the admin dashboard shows symptom counts, not what people typed", async ({ page }) => {
    await signInAs(page, fixtures().users.admin);
    await page.goto("/admin");
    const card = page.locator("#symptoms");
    await expect(card.getByRole("heading", { name: "How it is used" })).toBeVisible();
    await expect(card).not.toContainText(MARK.trim());
  });
});
