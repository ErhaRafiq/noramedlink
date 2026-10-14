import { expect, test } from "@playwright/test";
import { deflateSync } from "node:zlib";

import { fixtures } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

/** A small valid PNG, so the upload passes the backend's content check. */
function tinyPng(): Buffer {
  const width = 8;
  const height = 8;
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf: Buffer) => {
    let c = 0xffffffff;
    for (const byte of buf) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const body = Buffer.concat([Buffer.from(type), data]);
    const out = Buffer.alloc(body.length + 8);
    out.writeUInt32BE(data.length, 0);
    body.copy(out, 4);
    out.writeUInt32BE(crc(body), body.length + 4);
    return out;
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8; // bit depth
  header[9] = 0; // greyscale
  const rows = Buffer.alloc((width + 1) * height, 0xff);
  for (let y = 0; y < height; y++) rows[y * (width + 1)] = 0; // filter byte per row
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(rows)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

test.describe("patient dashboard", () => {
  test("lists the patient's reports and filters them with search", async ({ page }) => {
    const { users, run } = fixtures();
    await signInAs(page, users.patient);
    await page.goto("/dashboard/patient");
    const report = page.getByRole("button", { name: new RegExp(`^phase0-test-e2e blood panel ${run}`) });
    await expect(report).toBeVisible();
    // Its validation status is SAFE, which only means no rule raised an alert (AGENTS.md 6.2).
    await expect(report).toContainText("No rule alerts");
    await expect(report).not.toContainText(/SAFE|AI summarized/);

    const search = page.getByRole("searchbox", { name: "Search reports" });
    await search.fill("blood panel");
    await expect(page.getByRole("heading", { name: /Matching Reports/ })).toBeVisible();
    await expect(report).toBeVisible();

    await search.fill("no report has this title zzq");
    await expect(page.getByText("No reports match this search.")).toBeVisible();
    await page.getByRole("button", { name: "Clear filter" }).click();
    await expect(report).toBeVisible();
  });

  test("a new patient sees honest empty states", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    await expect(page.getByText("No reports uploaded yet.")).toBeVisible();
    await expect(page.getByText("No vitals recorded yet.")).toBeVisible();
    await expect(page.getByText("The app's checks have not marked anything in your reports.")).toBeVisible();
  });

  test("health flags come from the fixed rules, in everyday words, with no AI risk levels", async ({ page }) => {
    const { users, attentionReportId } = fixtures();
    await signInAs(page, users.patient);
    await page.goto("/dashboard/patient");
    const card = page.locator("#insights");
    await expect(card.getByRole("heading", { name: "Health flags" })).toBeVisible();
    await expect(card.getByText("Needs prompt attention", { exact: true })).toBeVisible();
    await expect(card.getByText(/Your kidney filtering rate \(eGFR\) reading of 25/)).toBeVisible();
    await expect(card.getByText("Diabetes")).toBeVisible();
    await card.getByRole("link", { name: /e2e attention panel/ }).click();
    await expect(page).toHaveURL(new RegExp(`/dashboard/patient/reports/${attentionReportId}$`));
    // The AI-set risk levels and the old doctor summary are no longer on the patient's dashboard.
    await page.goto("/dashboard/patient");
    await expect(page.getByRole("heading", { name: "Health summary" })).toHaveCount(0);
    await expect(page.getByText("Risk & Health Flags")).toHaveCount(0);
  });

  test("vitals: both values are required, then the reading is listed", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    const save = page.getByRole("button", { name: "Save Vitals" });
    await save.click();
    await expect(page.getByText("Enter both blood pressure and sugar level.")).toBeVisible();

    await page.getByLabel("Blood pressure").fill("128/84");
    await page.getByLabel("Sugar level").fill("104");
    await save.click();
    await expect(page.getByText("Vitals saved.")).toBeVisible();
    await expect(page.getByRole("cell", { name: "128/84" })).toBeVisible();
  });

  test("generates a one-time code for a doctor", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    await page.getByRole("button", { name: "Generate code" }).click();
    await expect(page.getByText("One-time code", { exact: true })).toBeVisible();
    await expect(page.getByText(/^\d{6}$/)).toBeVisible();
    await expect(page.getByRole("button", { name: "New code" })).toBeVisible();
  });

  test("uploading a report saves it and says honestly whether its text was read", async ({ page }) => {
    test.skip(fixtures().ocrKeySet || fixtures().aiKeySet, "would call OCR.space or an LLM (paid services)");
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/dashboard/patient");
    await page.locator("input[type=file]").first().setInputFiles({ name: "e2e-scan.png", mimeType: "image/png", buffer: tinyPng() });
    await page.getByLabel("Report title").fill("phase0-test e2e upload");
    await page.getByRole("button", { name: "Upload 1 File(s)" }).click();
    // No OCR key in this environment: the report is saved and the message says the text was not read.
    await expect(page.getByText("was saved, but its text could not be read")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Saved · text not read")).toBeVisible();
    await expect(page.getByText(/AI summary ready|AI Summary Generated/)).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^phase0-test e2e upload/ })).toBeVisible();
  });

  test("fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.patient);
    await page.goto("/dashboard/patient");
    await expect(page.getByRole("button", { name: new RegExp(`^phase0-test-e2e blood panel ${fixtures().run}`) })).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});
