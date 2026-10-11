import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

test.describe("admin doctor review", () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, fixtures().users.admin);
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Admin dashboard" })).toBeVisible();
  });

  test("reject asks for confirmation, and cancel keeps the doctor", async ({ page }) => {
    const doctor = fixtures().users.doctorPendingB;
    const row = page.locator("#doctors").getByRole("listitem").filter({ hasText: doctor.fullName });
    await row.getByRole("button", { name: "Reject" }).click();

    const dialog = page.getByRole("dialog", { name: "Reject this doctor?" });
    await expect(dialog).toContainText(doctor.fullName);
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
    await expect(row).toBeVisible();

    await row.getByRole("button", { name: "Reject" }).click();
    await dialog.getByRole("button", { name: "Reject doctor" }).click();
    await expect(row).toHaveCount(0);
  });

  test("approving a doctor removes them from the queue and makes them bookable", async ({ page }) => {
    const doctor = fixtures().users.doctorPendingA;
    const row = page.locator("#doctors").getByRole("listitem").filter({ hasText: doctor.fullName });
    await expect(row).toContainText("PMDC/PMC");
    await row.getByRole("button", { name: "Approve" }).click();
    await expect(row).toHaveCount(0);

    await page.goto("/doctors");
    await page.getByRole("searchbox", { name: "Search doctors" }).fill(doctor.fullName);
    await expect(page.getByRole("heading", { name: doctor.fullName })).toBeVisible();
  });

  test("fits a phone screen @mobile", async ({ page }) => {
    await expectNoHorizontalScroll(page);
  });
});
