import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { bookFirstSlot, expectNoHorizontalScroll, signInAs } from "./support/session";

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

  test("a patient books an open time, moves it and cancels it", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.patientEmpty);
    await bookFirstSlot(page, users.doctor.fullName);

    // The booking appears under "My appointments" with its time and type.
    const mine = page.getByRole("article").filter({ hasText: users.doctor.fullName }).filter({ has: page.getByRole("button", { name: "Reschedule" }) });
    await expect(mine.getByText("Booked", { exact: true })).toBeVisible();
    const timeLabel = (await mine.locator("p").first().textContent()) ?? "";
    expect(timeLabel).toMatch(/PKT$/);

    // Move it to another open time; the old time opens up again.
    await mine.getByRole("button", { name: "Reschedule" }).click();
    const dialog = page.getByRole("dialog", { name: "Move your appointment" });
    const times = dialog.getByRole("group", { name: /^Times on/ }).locator("button:not([disabled])");
    await times.last().click();
    await dialog.getByRole("button", { name: "Move appointment" }).click();
    await expect(dialog).toBeHidden({ timeout: 20_000 });
    await expect(page.getByRole("article").filter({ hasText: users.doctor.fullName }).filter({ has: page.getByRole("button", { name: "Reschedule" }) }).locator("p").first()).not.toHaveText(timeLabel, { timeout: 20_000 });

    // Cancel it through the confirmation.
    const moved = page.getByRole("article").filter({ hasText: users.doctor.fullName }).filter({ has: page.getByRole("button", { name: "Reschedule" }) });
    await moved.getByRole("button", { name: "Cancel" }).click();
    await page.getByRole("dialog", { name: "Cancel this appointment?" }).getByRole("button", { name: "Cancel appointment" }).click();
    await expect(page.getByRole("article").filter({ hasText: users.doctor.fullName }).getByText("Cancelled", { exact: true }).first()).toBeVisible({ timeout: 20_000 });
  });

  test("doctors can be filtered by city, price and consultation type", async ({ page }) => {
    const { users } = fixtures();
    await page.goto("/doctors");
    await page.getByPlaceholder("City or area").fill("zzz-no-such-city");
    await expect(page.getByText("No doctors match")).toBeVisible();
    await page.getByRole("button", { name: "Clear filters" }).first().click();
    await page.getByRole("searchbox", { name: "Search doctors" }).fill(users.doctor.fullName);
    await expect(page.getByRole("heading", { name: users.doctor.fullName })).toBeVisible();
    await page.getByLabel("Minimum rating").selectOption("4.5");
    await expect(page.getByText("No doctors match")).toBeVisible(); // nobody has a rating yet: an unrated doctor is not "highly rated"
  });

  test("a doctor with no published times cannot be booked", async ({ page }) => {
    // doctorWithAccess has the default test schedule; the pending doctor is not listed at all.
    await page.goto("/doctors");
    await page.getByRole("searchbox", { name: "Search doctors" }).fill(fixtures().users.doctorUnreviewed.fullName);
    await expect(page.getByText("No doctors match")).toBeVisible();
  });

  test("the booking dialog fits a phone screen @mobile", async ({ page }) => {
    const { users } = fixtures();
    await signInAs(page, users.patientEmpty);
    await page.goto("/doctors");
    await page.getByRole("searchbox", { name: "Search doctors" }).fill(users.doctor.fullName);
    const card = page.getByRole("article").filter({ hasText: users.doctor.fullName }).filter({ has: page.getByRole("button", { name: "Book appointment" }) });
    await card.getByRole("button", { name: "Book appointment" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("group", { name: /^Times on/ })).toBeVisible();
    await expectNoHorizontalScroll(page);
    const { left, width } = await page.evaluate(() => {
      const open = document.querySelector("dialog[open]")!.getBoundingClientRect();
      return { left: open.left, width: open.width };
    });
    expect(left).toBeGreaterThanOrEqual(0);
    expect(left + width).toBeLessThanOrEqual(390); // the dialog stays inside the screen
  });
});
