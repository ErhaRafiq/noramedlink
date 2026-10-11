import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { signInAs } from "./support/session";

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

  test("a signed-in patient can book an approved doctor", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.patientEmpty);
    await page.goto("/doctors");
    await page.getByRole("searchbox", { name: "Search doctors" }).fill(users.doctor.fullName);
    const card = page.getByRole("article").filter({ hasText: users.doctor.fullName });
    await card.getByRole("button", { name: "Book appointment" }).click();
    await expect(page.getByRole("status").filter({ hasText: /request|book/i }).first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(users.doctor.fullName).nth(1)).toBeVisible(); // now also in "My appointments"
  });
});
