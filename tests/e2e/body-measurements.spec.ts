import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

test.describe("weight and height", () => {
  test("a patient records, corrects and removes readings; the profile shows the latest values", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    const card = page.locator("#body-measurements");
    await expect(card.getByRole("heading", { name: "Weight and height" })).toBeVisible({ timeout: 30_000 });

    // Nothing is invented: no reading means "Not recorded" and an honest empty history.
    const latest = card.getByRole("region", { name: "Latest weight and height" });
    await expect(latest.getByText("Not recorded")).toHaveCount(3);
    await expect(card.getByText("No weight or height recorded yet.")).toBeVisible();

    const form = card.getByRole("form", { name: "Add a reading" });
    await form.getByRole("button", { name: "Save reading" }).click();
    await expect(form.getByText("Enter a weight, a height, or both.")).toBeVisible();

    await form.getByLabel("Weight", { exact: true }).fill("72.5");
    await form.getByLabel("Height (cm)").fill("170");
    await form.getByRole("button", { name: "Save reading" }).click();
    await expect(latest.getByText("72.5 kg")).toBeVisible();
    await expect(latest.getByText("170 cm")).toBeVisible();
    await expect(latest.getByText("25.1 kg/m²")).toBeVisible();
    await expect(latest.getByText("entered by you").first()).toBeVisible();
    // The patient's wording is neutral: a number and a reminder, no category.
    await expect(card.getByText("The BMI is a number from your weight and height")).toBeVisible();
    await expect(card.getByText(/underweight|overweight|obesity/i)).toHaveCount(0);

    // Pounds are converted and the server's range check is shown in words.
    await form.getByLabel("Weight", { exact: true }).fill("1");
    await form.getByRole("button", { name: "Save reading" }).click();
    await expect(form.getByRole("alert")).toBeVisible();
    await form.getByLabel("Weight", { exact: true }).fill("160");
    await form.getByLabel("Unit").selectOption("lb");
    await form.getByLabel("Height (cm)").fill("");
    await form.getByRole("button", { name: "Save reading" }).click();
    await expect(latest.getByText("72.57 kg")).toBeVisible();

    // Correct the newest reading.
    const history = card.getByRole("region", { name: "Weight and height history" });
    await history.getByRole("button", { name: /^Correct the reading of/ }).first().click();
    const edit = card.getByRole("form", { name: "Correct this reading" });
    await edit.getByLabel("Weight", { exact: true }).fill("73");
    await edit.getByRole("button", { name: "Save correction" }).click();
    await expect(latest.getByText("73 kg")).toBeVisible();

    // The profile shows the latest values.
    await page.goto("/profile");
    const profile = page.getByRole("region", { name: "Weight and height" });
    await expect(profile.getByText("73 kg")).toBeVisible({ timeout: 30_000 });
    await expect(profile.getByText("170 cm")).toBeVisible();
    await page.goto("/dashboard/patient");

    // Remove both readings, with a confirmation.
    const again = page.locator("#body-measurements");
    await expect(again.getByRole("heading", { name: "Weight and height" })).toBeVisible({ timeout: 30_000 });
    for (let left = 2; left > 0; left -= 1) {
      await again.getByRole("button", { name: /^Remove the reading of/ }).first().click();
      const dialog = page.getByRole("dialog", { name: "Remove this reading?" });
      if (left === 2) {
        await dialog.getByRole("button", { name: "Cancel" }).click();
        await again.getByRole("button", { name: /^Remove the reading of/ }).first().click();
      }
      await dialog.getByRole("button", { name: "Remove" }).click();
      await expect(again.getByRole("listitem")).toHaveCount(left - 1);
    }
    await expect(again.getByText("No weight or height recorded yet.")).toBeVisible();
  });

  test("a patient sets the pregnancy status", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    const status = page.locator("#body-measurements").getByRole("region", { name: "Pregnancy status" });
    await expect(status.getByText("Not recorded.")).toBeVisible({ timeout: 30_000 });
    await status.getByLabel("Status").selectOption("not_pregnant");
    await status.getByRole("button", { name: "Save status" }).click();
    await expect(status.getByText("Pregnancy status saved.")).toBeVisible();
    await expect(status.getByText(/Not pregnant, set on \d{4}-\d{2}-\d{2} by you/)).toBeVisible();
    await status.getByLabel("Status").selectOption("not_recorded");
    await status.getByRole("button", { name: "Save status" }).click();
    await expect(status.getByText("Not recorded.")).toBeVisible();
  });

  test("a doctor with access adds a reading; each side can change only its own", async ({ browser }) => {
    const { users } = fixtures();

    const patientContext = await browser.newContext();
    const patientPage = await patientContext.newPage();
    await signInAs(patientPage, users.patient);
    await patientPage.goto("/dashboard/patient");
    const mine = patientPage.locator("#body-measurements");
    await expect(mine.getByRole("heading", { name: "Weight and height" })).toBeVisible({ timeout: 30_000 });
    const patientForm = mine.getByRole("form", { name: "Add a reading" });
    await patientForm.getByLabel("Weight", { exact: true }).fill("68");
    await patientForm.getByLabel("Height (cm)").fill("160");
    await patientForm.getByRole("button", { name: "Save reading" }).click();
    await expect(mine.getByRole("region", { name: "Latest weight and height" }).getByText("68 kg")).toBeVisible();
    await patientContext.close();

    const doctorContext = await browser.newContext();
    const doctorPage = await doctorContext.newPage();
    await signInAs(doctorPage, users.doctorWithAccess);
    await doctorPage.goto("/dashboard/doctor");
    await doctorPage.getByRole("button", { name: new RegExp(`${users.patient.fullName} \\d+ reports?`) }).click();
    const card = doctorPage.locator("#body-measurements");
    await expect(card.getByRole("heading", { name: new RegExp(`Weight and height: ${users.patient.fullName}`) })).toBeVisible({ timeout: 30_000 });
    // The doctor sees the category and the Asian-population note, and cannot touch the patient's reading.
    await expect(card.getByText(/WHO adult band/i).or(card.getByText(/overweight|underweight|obesity|normal range/i)).first()).toBeVisible();
    await expect(card.getByText(/23\.0|27\.5/).first()).toBeVisible();
    await expect(card.getByRole("button", { name: /^Correct the reading of/ })).toHaveCount(0);

    const form = card.getByRole("form", { name: "Add a reading" });
    await form.getByLabel("Weight", { exact: true }).fill("69");
    await form.getByRole("button", { name: "Save reading" }).click();
    const history = card.getByRole("region", { name: "Weight and height history" });
    await expect(history.getByText(/entered by Dr /).first()).toBeVisible();
    await expect(history.getByRole("button", { name: /^Correct the reading of/ })).toHaveCount(1); // only the doctor's own
    await expect(card.getByRole("region", { name: "Pregnancy status" })).toBeVisible();
    await doctorContext.close();

    const againContext = await browser.newContext();
    const againPage = await againContext.newPage();
    await signInAs(againPage, users.patient);
    await againPage.goto("/dashboard/patient");
    const seen = againPage.locator("#body-measurements").getByRole("region", { name: "Weight and height history" });
    await expect(seen.getByText("Added by your doctor")).toBeVisible({ timeout: 30_000 });
    // The patient can correct their own reading but not the doctor's.
    await expect(seen.getByRole("button", { name: /^Correct the reading of/ })).toHaveCount(1);
    await againContext.close();
  });

  test("the medicine check says what weight it used and shows creatinine clearance for information only", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.doctorWithAccess);
    await page.goto("/dashboard/doctor");
    await page.getByRole("button", { name: new RegExp(`${users.patient.fullName} \\d+ reports?`) }).click();
    const body = page.locator("#body-measurements");
    await expect(body.getByRole("heading", { name: /Weight and height:/ })).toBeVisible({ timeout: 30_000 });
    const form = body.getByRole("form", { name: "Add a reading" });
    await form.getByLabel("Weight", { exact: true }).fill("71");
    await form.getByRole("button", { name: "Save reading" }).click();
    await expect(body.getByRole("region", { name: "Latest weight and height" }).getByText("71 kg")).toBeVisible();

    const card = page.locator("#prescribe");
    await card.getByRole("combobox", { name: "Add a medicine" }).fill("glucophag");
    await card.getByRole("option", { name: /Glucophage/ }).click();
    await expect(card.getByRole("region", { name: /Safety check: Glucophage/ })).toBeVisible({ timeout: 30_000 });
    await card.getByText("What the check used from this patient's record").click();
    await expect(card.getByText(/Weight: 71 kg on \d{4}-\d{2}-\d{2} \(entered by a doctor\)/)).toBeVisible();
    await expect(card.getByText(/Pregnancy status: /)).toBeVisible();
    await expect(card.getByLabel("Creatinine clearance (Cockcroft-Gault)")).toContainText("Information only");
  });

  test("weight and height fit a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    await expect(page.locator("#body-measurements").getByRole("heading", { name: "Weight and height" })).toBeVisible({ timeout: 30_000 });
    await expectNoHorizontalScroll(page);
  });
});
