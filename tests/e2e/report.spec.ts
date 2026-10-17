import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

test.describe("report page", () => {
  test("opens from the dashboard and shows the report", async ({ page }) => {
    const { users, run, reportId } = fixtures();
    await signInAs(page, users.patient);
    await page.goto("/dashboard/patient");
    await page.getByRole("button", { name: new RegExp(`^phase0-test-e2e blood panel ${run}`) }).click();
    await expect(page).toHaveURL(new RegExp(`/dashboard/patient/reports/${reportId}$`));
    await expect(page.getByRole("heading", { name: new RegExp(`e2e blood panel ${run}`) })).toBeVisible();
    await expect(page.getByLabel("Report text")).toHaveValue(/Hemoglobin 10\.2/);
    await expect(page.getByRole("button", { name: "Save changes" })).toBeDisabled(); // nothing edited yet
  });

  test("saving corrected text keeps it", async ({ page }) => {
    test.skip(fixtures().aiKeySet, "saving re-runs the AI summary (paid service)");
    const { users, reportId } = fixtures();
    await signInAs(page, users.patient);
    await page.goto(`/dashboard/patient/reports/${reportId}`);
    const text = page.getByLabel("Report text");
    await text.fill("Hemoglobin 11.4 g/dL. Allergies: none known. Corrected by the patient in an e2e test.");
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByRole("button", { name: "Save changes" })).toBeDisabled({ timeout: 45_000 });
    await page.reload();
    await expect(page.getByLabel("Report text")).toHaveValue(/Hemoglobin 11\.4/);
  });

  test("another patient's report is not found", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto(`/dashboard/patient/reports/${fixtures().reportId}`);
    await expect(page.getByText("Report not found", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Report text")).toHaveCount(0);
  });

  test("an invalid id shows the not-found page", async ({ page }) => {
    // app/loading.tsx makes this route stream, so Next keeps status 200 and renders not-found (with noindex).
    await signInAs(page, fixtures().users.patient);
    await page.goto("/dashboard/patient/reports/not-a-number");
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  });

  test("fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.patient);
    await page.goto(`/dashboard/patient/reports/${fixtures().reportId}`);
    await expect(page.getByLabel("Report text")).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});

test.describe("what needs attention on a report", () => {
  test("urgent alerts are red, cautions amber, and mentioned conditions are highlighted, in everyday words", async ({ page }) => {
    const { users, attentionReportId } = fixtures();
    await signInAs(page, users.patient);
    await page.goto(`/dashboard/patient/reports/${attentionReportId}`);

    const urgent = page.getByRole("alert", { name: "Needs prompt attention" });
    await expect(urgent).toBeVisible();
    await expect(urgent).toContainText("Your kidney filtering rate (eGFR) reading of 25");
    await expect(urgent).toContainText("call 1122");

    const caution = page.getByRole("region", { name: "Points to go over with your doctor" });
    await expect(caution).toContainText("blood sugar at any time of day");

    const conditions = page.getByRole("region", { name: "Conditions mentioned in your report" });
    await expect(conditions).toContainText("Diabetes");
    await expect(conditions).toContainText("long-term");
    await expect(conditions).toContainText("The app does not diagnose");
  });

  test("a report without alerts or conditions shows no attention panel", async ({ page }) => {
    const { users, reportId } = fixtures();
    await signInAs(page, users.patient);
    await page.goto(`/dashboard/patient/reports/${reportId}`);
    await expect(page.getByLabel("Report text")).toBeVisible();
    await expect(page.getByRole("alert", { name: "Needs prompt attention" })).toHaveCount(0);
  });

  test("the attention panel fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.patient);
    await page.goto(`/dashboard/patient/reports/${fixtures().attentionReportId}`);
    await expect(page.getByRole("alert", { name: "Needs prompt attention" })).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});
