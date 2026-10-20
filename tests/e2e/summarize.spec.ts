import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { alertWithText, expectNoHorizontalScroll, signInAs } from "./support/session";

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
    await expect(page.getByText(/Blood Pressure 145\/92 mmHg is raised/)).toBeVisible();
    // No AI key: the summary is labelled as rule-based, still advisory.
    await expect(page.getByText(/Built by fixed rules from the report text, not by AI\. Advisory only/)).toBeVisible();
  });

  test("too little text is refused before calling the API", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/summarize");
    await page.getByLabel("Report text").fill("short");
    await page.getByRole("button", { name: "Summarize", exact: true }).click();
    await expect(page.getByText("Enter at least 20 characters of report text.")).toBeVisible();
  });
});

test.describe("reading a file or photo on the Summarize page", () => {
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAEUlEQVR4nGP8//8/AzYwOgR4AABv0wP/dUh5uwAAAABJRU5ErkJggg==",
    "base64",
  );

  test("the text read from a photo fills the box, and unsure numbers are listed to check", async ({ page }) => {
    await signInAs(page, fixtures().users.patient);
    await page.route("**/api/backend/nlp/read-file", (route) =>
      route.fulfill({
        json: {
          text: "Hemoglobin 10.2 g/dL\nGlucose 8 mg/dL",
          truncated: false,
          source: "ocr",
          confidence: 0.9,
          uncertain: ["8 (in: Glucose 8 mg/dL)"],
          uncertain_count: 1,
        },
      }),
    );
    await page.goto("/summarize");
    await page.getByLabel("Take a photo of the report").setInputFiles({ name: "photo.png", mimeType: "image/png", buffer: png });
    await expect(page.getByText("Read photo.png")).toBeVisible();
    await expect(page.getByText("8 (in: Glucose 8 mg/dL)")).toBeVisible();
    await expect(page.getByLabel("Report text")).toHaveValue(/Hemoglobin 10.2 g\/dL/);
    await expectNoHorizontalScroll(page);
  });

  test("a photo that cannot be read says what to do, and a real unreadable image is refused by the server", async ({ page }) => {
    await signInAs(page, fixtures().users.patient);
    await page.goto("/summarize");
    await page.getByLabel("Choose a report file").setInputFiles({ name: "broken.png", mimeType: "image/png", buffer: Buffer.from("not an image") });
    await expect(alertWithText(page, "appears corrupted")).toBeVisible({ timeout: 20_000 });
  });

  test("signed-out visitors see no file picker", async ({ page }) => {
    await page.goto("/summarize");
    await expect(page.getByText("Sign in to summarize reports")).toBeVisible();
    await expect(page.getByLabel("Choose a report file")).toHaveCount(0);
  });

  test("the file picker fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.patient);
    await page.goto("/summarize");
    await expect(page.getByRole("button", { name: "Take a photo" })).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});
