import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

test.describe("a report explained in everyday words", () => {
  test("each result says where it sits, with the machine-generated note, and fits the screen", async ({ page }) => {
    const { users, attentionReportId } = fixtures();
    await signInAs(page, users.patient);
    await page.goto(`/dashboard/patient/reports/${attentionReportId}`);

    const card = page.getByRole("region", { name: "Each result" });
    await expect(card).toBeVisible();
    await expect(card).toContainText("Kidney filtering rate");
    await expect(card).toContainText("Lower than the usual range");
    await expect(card.getByRole("img").first()).toBeVisible();
    await expect(page.getByText("Written by a computer program, not a doctor")).toBeVisible();

    await expectNoHorizontalScroll(page);
  });

  test("explain more and a typed question are answered, and an emergency gets the 1122 message", async ({ page }) => {
    const { users, attentionReportId } = fixtures();
    await signInAs(page, users.patient);
    await page.goto(`/dashboard/patient/reports/${attentionReportId}`);

    await page.getByRole("button", { name: /Explain .* more/ }).first().click();
    await expect(page.getByText("Looking at your report").or(page.getByText("What it is:"))).toBeVisible();
    await expect(page.getByText("What it is:").first()).toBeVisible();

    const box = page.getByLabel("Your question about this report");
    await box.fill("What medicine should I take?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByText("cannot give advice about treatment")).toBeVisible();

    await box.fill("I have chest pain and cannot breathe");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByText("1122").first()).toBeVisible();
    await expect(page.getByText("This is not an emergency service.")).toBeVisible();

    await page.getByRole("button", { name: "Clear this conversation" }).click();
    await expect(page.getByText("cannot give advice about treatment")).toHaveCount(0);
  });

  test("the explanation and the question box fit a phone screen @mobile", async ({ page }) => {
    const { users, attentionReportId } = fixtures();
    await signInAs(page, users.patient);
    await page.goto(`/dashboard/patient/reports/${attentionReportId}`);
    await expect(page.getByRole("region", { name: "Each result" })).toBeVisible();
    await page.getByLabel("Your question about this report").fill("What does my eGFR mean?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByText("What it is:").first()).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});
