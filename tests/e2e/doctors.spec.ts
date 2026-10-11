import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { alertWithText, signInAs } from "./support/session";

test.describe("find a doctor", () => {
  test("lists approved doctors only, and search narrows the list", async ({ page }) => {
    const { users } = fixtures();
    await page.goto("/doctors");
    const search = page.getByRole("searchbox", { name: "Search doctors" });

    await search.fill(users.doctor.fullName);
    await expect(page.getByRole("heading", { name: users.doctor.fullName })).toBeVisible();

    await search.fill(users.doctorUnreviewed.fullName); // pending: not listed
    await expect(page.getByText("No doctors match")).toBeVisible();

    await search.fill("zzq no doctor has this name");
    await expect(page.getByText("No doctors match")).toBeVisible();
  });

  test("a patient books, reschedules and cancels an appointment", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.patientEmpty);
    await page.goto("/doctors");
    await page.getByRole("searchbox", { name: "Search doctors" }).fill(users.doctor.fullName);
    const card = page.getByRole("article").filter({ hasText: users.doctor.fullName }).filter({ has: page.getByRole("button", { name: "Book appointment" }) });
    await card.getByRole("button", { name: "Book appointment" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Appointment booked" }).first()).toBeVisible({ timeout: 20_000 });

    // The appointment appears under "My appointments".
    const booked = page.getByRole("article").filter({ hasText: users.doctor.fullName }).filter({ has: page.getByRole("button", { name: "Reschedule" }) });
    const when = booked.locator("p").first();
    const before = await when.textContent();

    const next = new Date(Date.now() + 5 * 24 * 3600 * 1000);
    const local = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-${String(next.getDate()).padStart(2, "0")}T11:30`;
    await booked.getByLabel("New date and time").fill(local);
    await booked.getByRole("button", { name: "Reschedule" }).click();
    await expect(when).not.toHaveText(before ?? "", { timeout: 20_000 });
    await expect(alertWithText(page, "Patients can only cancel")).toHaveCount(0);

    await booked.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByRole("article").filter({ hasText: users.doctor.fullName }).getByText("cancelled")).toBeVisible();
  });
});
