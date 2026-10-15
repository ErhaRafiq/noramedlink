import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { alertWithText, expectNoHorizontalScroll, signInAs } from "./support/session";

const INVALID_CODE = "Invalid or expired patient dashboard OTP.";

test.describe("doctor access to a patient file", () => {
  test("a wrong code is refused", async ({ page }) => {
    await signInAs(page, fixtures().users.doctor);
    await page.goto("/dashboard/doctor");
    await page.getByLabel("One-time code").fill("000000");
    await page.getByRole("button", { name: "Unlock file" }).click();
    await expect(alertWithText(page, INVALID_CODE)).toBeVisible();
    await expect(page.getByText(/e2e blood panel/)).toHaveCount(0);
  });

  test("patient code → doctor unlocks the file → doctor ends access", async ({ browser }) => {
    const { users, run } = fixtures();

    const patientContext = await browser.newContext();
    const patientPage = await patientContext.newPage();
    await signInAs(patientPage, users.patient);
    await patientPage.goto("/dashboard/patient");
    await patientPage.getByRole("button", { name: "Generate code" }).click();
    const code = (await patientPage.getByText(/^\d{6}$/).textContent())?.trim() ?? "";
    expect(code).toMatch(/^\d{6}$/);
    await patientContext.close();

    const doctorContext = await browser.newContext();
    const page = await doctorContext.newPage();
    await signInAs(page, users.doctor);
    await page.goto("/dashboard/doctor");
    await page.getByLabel("One-time code").fill(code);
    await page.getByRole("button", { name: "Unlock file" }).click();

    // The patient's own report appears in the opened file.
    await expect(page.getByText(new RegExp(`e2e blood panel ${run}`))).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(users.patient.fullName).first()).toBeVisible();

    // The code works once.
    await page.getByLabel("One-time code").fill(code);
    await page.getByRole("button", { name: "Unlock file" }).click();
    await expect(alertWithText(page, INVALID_CODE)).toBeVisible();

    await page.getByRole("button", { name: "End consultation" }).click();
    await expect(page.getByText(new RegExp(`e2e blood panel ${run}`))).toHaveCount(0, { timeout: 30_000 });
    await doctorContext.close();
  });

  test("the doctor dashboard fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.doctor);
    await page.goto("/dashboard/doctor");
    await expect(page.getByLabel("One-time code")).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});

test.describe("clinical summary for the doctor", () => {
  test("builds the patient's summary by fixed rules, with flags, sources and versions", async ({ page }) => {
    test.skip(fixtures().aiKeySet, "regenerating asks the AI to word the key findings (paid service)");
    const { users } = fixtures();
    await signInAs(page, users.doctorWithAccess);
    await page.goto("/dashboard/doctor");
    await page.getByRole("button", { name: new RegExp(users.patient.fullName) }).click();

    const card = page.locator("#clinical-summary");
    await expect(card.getByText("Up to date")).toBeVisible({ timeout: 30_000 });
    await expect(card.getByRole("heading", { name: users.patient.fullName })).toBeVisible();
    const abnormal = card.getByRole("region", { name: "Abnormal results" });
    await expect(abnormal).toContainText("eGFR 25");
    await expect(abnormal).toContainText("Why:");
    await expect(abnormal).toContainText("Source:");
    await expect(card.getByRole("region", { name: "Conditions mentioned in reports" })).toContainText("diabetes mellitus");
    await expect(card.getByText("Built by fixed rules from the patient's records.", { exact: true })).toBeVisible();

    // Nothing changed: regenerating keeps the same version.
    await card.getByRole("button", { name: "Regenerate" }).click();
    await expect(card.getByText("Up to date")).toBeVisible();
    await expect(card.getByText(/^Version 1 ·/)).toBeVisible();
    await expect(card.getByLabel("Version")).toHaveValue("1");
  });

  test("the clinical summary fits a phone screen @mobile", async ({ page }) => {
    test.skip(fixtures().aiKeySet, "regenerating asks the AI to word the key findings (paid service)");
    const { users } = fixtures();
    await signInAs(page, users.doctorWithAccess);
    await page.goto("/dashboard/doctor");
    await page.getByRole("button", { name: new RegExp(users.patient.fullName) }).click();
    await expect(page.locator("#clinical-summary").getByText("Abnormal results")).toBeVisible({ timeout: 30_000 });
    await expectNoHorizontalScroll(page);
  });
});

test.describe("prescribing with the medication-safety check", () => {
  test("a contraindicated medicine is flagged, a ranked alternative replaces it, and the patient sees the prescription", async ({ browser }) => {
    const { users } = fixtures();
    const doctorContext = await browser.newContext();
    const page = await doctorContext.newPage();
    await signInAs(page, users.doctorWithAccess);
    await page.goto("/dashboard/doctor");
    await page.getByRole("button", { name: new RegExp(users.patient.fullName) }).click();

    const card = page.locator("#prescribe");
    await card.getByRole("combobox", { name: "Add a medicine" }).fill("glucophag");
    await card.getByRole("option", { name: /Glucophage/ }).click();
    const check = card.getByRole("region", { name: /Safety check: Glucophage/ });
    await expect(check).toContainText("Contraindicated", { timeout: 30_000 });
    await expect(check).toContainText("metformin with eGFR < 30");
    await expect(check).toContainText("Why: Latest eGFR: 25");
    await expect(check).toContainText("Safer alternatives for this patient, ranked");

    // Choose the first ranked alternative; it is re-checked and needs no justification.
    await check.getByRole("button", { name: "Use instead" }).first().click();
    await expect(card.getByText("Chosen instead of Glucophage.")).toBeVisible();
    await expect(card.getByText(/high-risk alert\(s\) need your written reason/)).toHaveCount(0, { timeout: 30_000 });
    await card.getByRole("button", { name: "Confirm prescription" }).click();
    await expect(card.getByText("Prescription saved.")).toBeVisible({ timeout: 30_000 });
    await expect(card.getByRole("heading", { name: "Prescriptions for this patient" })).toBeVisible();
    await doctorContext.close();

    const patientContext = await browser.newContext();
    const patientPage = await patientContext.newPage();
    await signInAs(patientPage, users.patient);
    await patientPage.goto("/dashboard/patient");
    const mine = patientPage.locator("#prescriptions");
    await expect(mine.getByRole("heading", { name: "Prescriptions from your doctors" })).toBeVisible();
    await expect(mine).toContainText(users.doctorWithAccess.fullName);
    await expect(mine).toContainText(/once a day/i);
    await patientContext.close();
  });

  test("a high-risk alert needs a written reason before the prescription is confirmed", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.doctorWithAccess);
    await page.goto("/dashboard/doctor");
    await page.getByRole("button", { name: new RegExp(users.patient.fullName) }).click();
    const card = page.locator("#prescribe");
    await card.getByRole("combobox", { name: "Add a medicine" }).fill("brufen");
    await card.getByRole("option", { name: /Brufen/ }).click();
    await expect(card.getByText(/high-risk alert\(s\) need your written reason/)).toBeVisible({ timeout: 30_000 });
    await card.getByRole("button", { name: "Confirm prescription" }).click();

    const dialog = page.getByRole("dialog", { name: "Prescribe despite high-risk alerts?" });
    const confirm = dialog.getByRole("button", { name: "Confirm with these reasons" });
    await expect(confirm).toBeDisabled();
    // One reason per high-risk alert (the optional notes box gets one too).
    for (const field of await dialog.getByRole("textbox").all()) {
      await field.fill("Short course agreed with the patient; kidney function rechecked in 3 days.");
    }
    await expect(confirm).toBeEnabled();
    await confirm.click();
    await expect(card.getByText("Prescription saved.")).toBeVisible({ timeout: 30_000 });
    await expect(card.getByText(/alert\(s\) overridden/).first()).toBeVisible();
  });

  test("the prescribing panel fits a phone screen @mobile", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.doctorWithAccess);
    await page.goto("/dashboard/doctor");
    await page.getByRole("button", { name: new RegExp(users.patient.fullName) }).click();
    const card = page.locator("#prescribe");
    await card.getByRole("combobox", { name: "Add a medicine" }).fill("glucophag");
    await card.getByRole("option", { name: /Glucophage/ }).click();
    await expect(card.getByText("Safer alternatives for this patient, ranked")).toBeVisible({ timeout: 30_000 });
    await expectNoHorizontalScroll(page);
  });
});
