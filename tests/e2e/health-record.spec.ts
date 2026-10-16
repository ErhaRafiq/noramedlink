import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

test.describe("health record", () => {
  test("a patient adds, resolves and removes entries, and is told which words the medication check cannot use", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    const card = page.locator("#health-record");
    await expect(card.getByRole("heading", { name: "My health record" })).toBeVisible({ timeout: 30_000 });
    await expect(card.getByText("No allergy recorded.")).toBeVisible();

    const form = card.getByRole("form", { name: "Add to the health record" });
    await form.getByLabel("Allergic to").fill("penicillin");
    await form.getByLabel("How serious (optional)").selectOption("severe");
    await form.getByRole("button", { name: "Add to the record" }).click();
    const allergies = card.getByRole("region", { name: "Allergies" });
    await expect(allergies.getByText("penicillin")).toBeVisible();
    await expect(allergies.getByText("severe", { exact: true })).toBeVisible();

    // The same allergy again is refused in words.
    await form.getByLabel("Allergic to").fill("Penicillin");
    await form.getByRole("button", { name: "Add to the record" }).click();
    await expect(form.getByText("This is already on the list.")).toBeVisible();

    // A diagnosis the medication check has never heard of is kept, with an honest note.
    await form.getByLabel("Type").selectOption("diagnosis");
    await form.getByLabel("Name").fill("feeling sad on mondays");
    await form.getByRole("button", { name: "Add to the record" }).click();
    const diagnoses = card.getByRole("region", { name: "Diagnoses" });
    await expect(diagnoses.getByText("feeling sad on mondays")).toBeVisible();
    await expect(diagnoses.getByText("Not used by the check")).toBeVisible();
    await expect(card.getByText("Some entries are not used by the medication check")).toBeVisible();
    await expect(card.getByText("feeling sad on mondays stays on the record for doctors to read, but is not checked")).toBeVisible();

    await allergies.getByRole("button", { name: "Mark as resolved: penicillin" }).click();
    await expect(allergies.getByText("Resolved", { exact: true })).toBeVisible();
    await allergies.getByRole("button", { name: "Mark as current again: penicillin" }).click();
    await expect(allergies.getByText("Resolved", { exact: true })).toHaveCount(0);

    await diagnoses.getByRole("button", { name: "Remove feeling sad on mondays" }).click();
    const dialog = page.getByRole("dialog", { name: "Remove this entry?" });
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(diagnoses.getByText("feeling sad on mondays")).toBeVisible();
    await diagnoses.getByRole("button", { name: "Remove feeling sad on mondays" }).click();
    await dialog.getByRole("button", { name: "Remove" }).click();
    await expect(diagnoses.getByText("feeling sad on mondays")).toHaveCount(0);
    await expect(card.getByText("No diagnosis recorded.")).toBeVisible();
  });

  test("a doctor with access adds an entry the patient sees, and it shows in the patient's access history", async ({ browser }) => {
    const { users } = fixtures();
    const doctorContext = await browser.newContext();
    const doctorPage = await doctorContext.newPage();
    await signInAs(doctorPage, users.doctorWithAccess);
    await doctorPage.goto("/dashboard/doctor");
    await doctorPage.getByRole("button", { name: new RegExp(users.patient.fullName) }).click();

    const card = doctorPage.locator("#health-record");
    await expect(card.getByRole("heading", { name: new RegExp(`Allergies and conditions: ${users.patient.fullName}`) })).toBeVisible({ timeout: 30_000 });
    const form = card.getByRole("form", { name: "Add to the health record" });
    await form.getByLabel("Allergic to").fill("shellfish");
    await form.getByRole("button", { name: "Add to the record" }).click();
    await expect(card.getByText(`Added by ${users.doctorWithAccess.fullName}`)).toBeVisible();
    await expect(card.getByRole("button", { name: /^Remove / })).toHaveCount(0); // doctors cannot remove entries
    await doctorContext.close();

    const patientContext = await browser.newContext();
    const patientPage = await patientContext.newPage();
    await signInAs(patientPage, users.patient);
    await patientPage.goto("/dashboard/patient");
    const mine = patientPage.locator("#health-record");
    const shellfish = mine.getByRole("region", { name: "Allergies" });
    await expect(shellfish.getByText("shellfish").first()).toBeVisible({ timeout: 30_000 });
    await expect(shellfish.getByText(`Added by ${users.doctorWithAccess.fullName}`)).toBeVisible();

    const history = patientPage.locator("#access-history");
    await expect(history.getByRole("heading", { name: "Who has seen my record" })).toBeVisible();
    await expect(history.getByText(users.doctorWithAccess.fullName).first()).toBeVisible();
    await expect(history.getByText(/added to your health record/).first()).toBeVisible();
    await expect(history.getByText(/viewed your record/).first()).toBeVisible();
    await patientContext.close();
  });

  test("a patient with no one having opened their record sees an honest empty history", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    await expect(page.locator("#access-history").getByText("No doctor or administrator has opened or changed your record yet.")).toBeVisible({ timeout: 30_000 });
  });

  test("the patient's record and access history fit a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    await expect(page.locator("#health-record").getByRole("heading", { name: "My health record" })).toBeVisible({ timeout: 30_000 });
    await expectNoHorizontalScroll(page);
  });
});

test.describe("audit log (admin)", () => {
  test("the administrator filters who accessed or changed records", async ({ page }) => {
    await signInAs(page, fixtures().users.admin);
    await page.goto("/admin");
    const log = page.locator("#audit-log");
    await expect(log.getByRole("heading", { name: "Who accessed or changed records" })).toBeVisible({ timeout: 30_000 });
    await expect(log.getByText(/Showing \d+ of \d+/)).toBeVisible();

    await log.getByLabel("What happened").selectOption({ label: "added to the health record" });
    const rows = log.getByRole("list");
    await expect(rows.getByText("added to the health record").first()).toBeVisible();
    await expect(rows.getByText("viewed the patient's record")).toHaveCount(0);

    await log.getByLabel("About patient number").fill("999999999");
    await expect(log.getByText("Nothing matches these filters")).toBeVisible();
    await log.getByRole("button", { name: "Clear filters" }).click();
    await expect(log.getByText(/Showing \d+ of \d+/)).toBeVisible();
  });

  test("the audit log fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.admin);
    await page.goto("/admin");
    await expect(page.locator("#audit-log").getByRole("heading", { name: "Who accessed or changed records" })).toBeVisible({ timeout: 30_000 });
    await expectNoHorizontalScroll(page);
  });

  test("a patient cannot open the audit log through the app", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/admin");
    await expect(page).not.toHaveURL(/\/admin$/);
  });
});
