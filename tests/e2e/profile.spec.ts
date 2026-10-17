import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

test.describe("my profile", () => {
  test("a patient saves their details and sees their age", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: "My profile" })).toBeVisible();

    const details = page.getByRole("region", { name: "Personal details" });
    await details.getByLabel("Date of birth").fill("1990-05-17");
    await details.getByLabel("Gender").selectOption("Female");
    await details.getByLabel("Blood group").selectOption("O+");
    await details.getByLabel("City").fill("Lahore");
    await details.getByLabel("Emergency contact name").fill("Test Contact");
    await details.getByRole("button", { name: "Save details" }).click();
    await expect(details.getByText("Your details were saved.")).toBeVisible({ timeout: 20_000 });

    await page.reload();
    const again = page.getByRole("region", { name: "Personal details" });
    await expect(again.getByLabel("City")).toHaveValue("Lahore");
    await expect(again.getByLabel("Blood group")).toHaveValue("O+");
    await expect(again.getByText(/Age \d+/)).toBeVisible();
    await expect(again.getByText(/\*{5}-\*{7}-\d/)).toBeVisible(); // the CNIC is masked
  });

  test("a bad date or phone is explained before anything is sent", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/profile");
    const account = page.getByRole("region", { name: "Account" });
    await account.getByLabel("Phone").fill("12");
    await account.getByRole("button", { name: "Save account" }).click();
    await expect(account.getByText("Enter a phone number with at least 7 digits.")).toBeVisible();
  });

  test("a doctor edits their public profile; specialization is locked", async ({ page }) => {
    await signInAs(page, fixtures().users.doctorWithAccess);
    await page.goto("/profile");
    const form = page.getByRole("region", { name: "Doctor profile" });
    await expect(form.getByLabel("Specialization")).toHaveAttribute("readonly", "");
    await expect(form.getByLabel("PMDC / PMC number")).toHaveAttribute("readonly", "");
    await form.getByLabel("Qualifications").fill("MBBS, FCPS");
    await form.getByLabel("Years of experience").fill("9");
    await form.getByLabel("Languages").fill("Urdu, English");
    await form.getByLabel("Consultation fee (PKR)").fill("50");
    await form.getByRole("button", { name: "Save doctor profile" }).click();
    await expect(form.getByText(/PKR 200 to PKR 100,000/)).toBeVisible(); // refused before it is sent
    await form.getByLabel("Consultation fee (PKR)").fill("2000");
    await form.getByRole("button", { name: "Save doctor profile" }).click();
    await expect(form.getByText("Your doctor profile was saved.")).toBeVisible({ timeout: 20_000 });
  });

  test("patients see a doctor's profile details when they search", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.doctor);
    await page.goto("/profile");
    const form = page.getByRole("region", { name: "Doctor profile" });
    await form.getByLabel("Qualifications").fill("MBBS, MRCP");
    await form.getByLabel("Languages").fill("Urdu, Punjabi");
    await form.getByRole("button", { name: "Save doctor profile" }).click();
    await expect(form.getByText("Your doctor profile was saved.")).toBeVisible({ timeout: 20_000 });

    const patient = await page.context().browser()!.newContext();
    const patientPage = await patient.newPage();
    await signInAs(patientPage, users.patientEmpty);
    await patientPage.goto("/doctors");
    await patientPage.getByRole("searchbox", { name: "Search doctors" }).fill(users.doctor.fullName);
    const card = patientPage.getByRole("article").filter({ hasText: users.doctor.fullName }).filter({ has: patientPage.getByRole("button", { name: "Book appointment" }) });
    await expect(card.getByText("MBBS, MRCP")).toBeVisible();
    await expect(card.getByText("Urdu, Punjabi")).toBeVisible();
    await expect(card).not.toContainText("PMDC");
    await patient.close();
  });

  test("the profile page fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.doctorWithAccess);
    await page.goto("/profile");
    await expect(page.getByRole("region", { name: "Doctor profile" })).toBeVisible();
    await expectNoHorizontalScroll(page);
  });

  test("signed-out visitors are sent to sign in", async ({ page }) => {
    await page.goto("/profile");
    await expect(page).toHaveURL(/\/login\?next=\%2Fprofile/);
  });
});
