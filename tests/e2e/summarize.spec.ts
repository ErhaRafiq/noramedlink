import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { signInAs } from "./support/session";

test.describe("summarize a report", () => {
  test("asks visitors to sign in", async ({ page }) => {
    await page.goto("/summarize");
    await expect(page.getByText("Sign in to summarize reports")).toBeVisible();
  });

  test("the breakdown comes from the server: values, rule alerts, next steps", async ({ page }) => {
    test.skip(fixtures().aiKeySet, "would call an LLM (paid service)");
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/summarize");
    await page.getByRole("button", { name: "Use example" }).click();
    await page.getByRole("button", { name: "Summarize", exact: true }).click();

    await expect(page.getByText("Hemoglobin: 10.8 g/dL")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Stated as absent: chest pain")).toBeVisible();
    await expect(page.getByText(/Blood pressure text appears elevated/)).toBeVisible();
    await expect(page.getByText("AI-generated and advisory only.", { exact: false }).first()).toBeVisible();
  });

  test("too little text is refused before calling the API", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/summarize");
    await page.getByLabel("Report text").fill("short");
    await page.getByRole("button", { name: "Summarize", exact: true }).click();
    await expect(page.getByText("Enter at least 20 characters of report text.")).toBeVisible();
  });
});
