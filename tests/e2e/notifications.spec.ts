import { expect, test, type Page } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { bookFirstSlot, expectNoHorizontalScroll, signInAs } from "./support/session";

// The bell checks every 30 seconds; a "focus" event makes it check at once, so the tests do not wait.
const nudge = (page: Page) => page.evaluate(() => window.dispatchEvent(new Event("focus")));

test.describe("the bell, the toasts and the panel", () => {
  test("a new booking reaches the doctor as a toast, then in the bell panel, and can be read from there", async ({ browser }) => {
    test.setTimeout(150_000);
    const { users } = fixtures();
    const doctorContext = await browser.newContext();
    const doctor = await doctorContext.newPage();
    await signInAs(doctor, users.doctorWithAccess);
    await doctor.goto("/dashboard/doctor");
    await expect(doctor.getByRole("button", { name: /^Notifications/ }).first()).toBeVisible({ timeout: 60_000 });
    await doctor.waitForTimeout(1500); // the first check sets the baseline: old notifications never toast

    const patientContext = await browser.newContext();
    const patient = await patientContext.newPage();
    await signInAs(patient, users.patient);
    await bookFirstSlot(patient, users.doctorWithAccess.fullName);
    await patientContext.close();

    await nudge(doctor);
    const toast = doctor.getByRole("region", { name: "New notifications" }).getByRole("status").filter({ hasText: "New appointment" });
    await expect(toast).toBeVisible({ timeout: 20_000 });
    await expect(doctor.getByRole("button", { name: /Notifications, \d+ unread/ }).first()).toBeVisible();

    // The panel lists it, unread, with its own page to go to.
    await doctor.getByRole("button", { name: /Notifications, \d+ unread/ }).first().click();
    const panel = doctor.getByRole("dialog", { name: "Notifications" });
    const item = panel.getByRole("link").filter({ hasText: "New appointment" }).first();
    await expect(item).toBeVisible();
    await expect(item).toContainText("(unread)");
    await expect(item).toHaveAttribute("href", "/dashboard/doctor#appointments");

    await panel.getByRole("tab", { name: /Unread/ }).click();
    await expect(panel.getByRole("link").filter({ hasText: "New appointment" }).first()).toBeVisible();
    await panel.getByRole("button", { name: "Mark all read" }).click();
    await expect(doctor.getByRole("button", { name: "Notifications", exact: true }).first()).toBeVisible(); // no count any more
    await expect(panel.getByText("You are all caught up")).toBeVisible();
    await doctorContext.close();
  });

  test("the panel opens from the keyboard, closes with Escape and gives focus back to the bell", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/doctors");
    const bell = page.getByRole("button", { name: /^Notifications/ }).first();
    await bell.focus();
    await page.keyboard.press("Enter");
    const panel = page.getByRole("dialog", { name: "Notifications" });
    await expect(panel).toBeVisible();
    await expect(bell).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("Escape");
    await expect(panel).toBeHidden();
    await expect(bell).toBeFocused();
  });

  test("a click outside closes the panel, and opening an item goes to its page and closes it", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/doctors");
    await page.getByRole("button", { name: /^Notifications/ }).first().click();
    const panel = page.getByRole("dialog", { name: "Notifications" });
    await expect(panel).toBeVisible();
    await page.getByRole("heading", { name: "Find a doctor" }).click();
    await expect(panel).toBeHidden();

    await page.getByRole("button", { name: /^Notifications/ }).first().click();
    await panel.getByRole("link", { name: "See all notifications" }).click();
    await expect(page).toHaveURL(/\/notifications$/);
    await expect(panel).toBeHidden();
  });

  test("a visitor who is not signed in has no bell and the page asks the server nothing about notifications", async ({ page }) => {
    const asked: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/notifications")) asked.push(request.url());
    });
    await page.goto("/doctors");
    await page.waitForTimeout(1500);
    await expect(page.getByRole("button", { name: /^Notifications/ })).toHaveCount(0);
    expect(asked).toEqual([]);
  });

  test("the panel fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/doctors");
    await page.getByRole("button", { name: /^Notifications/ }).first().click();
    const panel = page.getByRole("dialog", { name: "Notifications" });
    await expect(panel).toBeVisible();
    const box = await panel.boundingBox();
    expect(box && box.x >= 0 && box.x + box.width <= 390).toBeTruthy();
    await expectNoHorizontalScroll(page);
  });
});

test.describe("the notifications page", () => {
  test("filters by read state and type, groups by day, and dismisses one", async ({ page }) => {
    test.setTimeout(120_000);
    const { users } = fixtures();
    await signInAs(page, users.patientEmpty);
    await bookFirstSlot(page, users.doctor.fullName); // gives this patient a notification of their own
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "Notifications", level: 1 })).toBeVisible({ timeout: 30_000 });
    const all = page.getByRole("list").first();
    await expect(page.getByRole("heading", { name: /^(Today|Yesterday)$/ }).first()).toBeVisible();

    const countBefore = await page.getByRole("button", { name: /^Dismiss:/ }).count();
    expect(countBefore).toBeGreaterThan(0);
    await page.getByRole("button", { name: /^Dismiss:/ }).first().click();
    await expect(page.getByRole("button", { name: /^Dismiss:/ })).toHaveCount(countBefore - 1);

    await page.getByRole("button", { name: "Payments" }).click();
    await expect(page.getByText("Nothing in this group")).toBeVisible();
    await page.getByRole("button", { name: "Everything" }).click();
    await expect(all).toBeVisible();

    const markAll = page.getByRole("button", { name: "Mark all read" });
    if (await markAll.isEnabled()) await markAll.click(); // disabled when the dismissed one was the only unread
    await page.getByRole("tab", { name: /Unread/ }).click();
    await expect(page.getByText("You are all caught up")).toBeVisible();
    await expect(page.getByRole("button", { name: "Notifications", exact: true }).first()).toBeVisible(); // no count on the bell
  });

  test("an admin sees admin and account types, not patient ones", async ({ page }) => {
    await signInAs(page, fixtures().users.admin);
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "Notifications", level: 1 })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Admin", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Payments" })).toHaveCount(0);
  });

  test("the page fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "Notifications", level: 1 })).toBeVisible({ timeout: 30_000 });
    await expectNoHorizontalScroll(page);
  });
});
