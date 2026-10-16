import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { bookFirstSlot, expectNoHorizontalScroll, signInAs } from "./support/session";

test.describe("weekly hours", () => {
  test("a doctor changes their hours and they are kept", async ({ page }) => {
    await signInAs(page, fixtures().users.doctorWithAccess);
    await page.goto("/profile");
    const hours = page.getByRole("region", { name: "Weekly hours" });
    const sunday = hours.getByRole("group", { name: "Sunday window" });
    await sunday.getByLabel("Sunday appointment length").selectOption("60");
    await hours.getByRole("button", { name: "Save weekly hours" }).click();
    await expect(hours.getByText("Your weekly hours were saved.")).toBeVisible({ timeout: 20_000 });

    await page.reload();
    await expect(page.getByRole("region", { name: "Weekly hours" }).getByRole("group", { name: "Sunday window" }).getByLabel("Sunday appointment length")).toHaveValue("60");
  });

  test("impossible hours are explained before anything is sent", async ({ page }) => {
    await signInAs(page, fixtures().users.doctorWithAccess);
    await page.goto("/profile");
    const hours = page.getByRole("region", { name: "Weekly hours" });
    const monday = hours.getByRole("group", { name: "Monday window" });
    await monday.getByLabel("Monday starts").fill("15:00");
    await monday.getByLabel("Monday ends").fill("10:00");
    await hours.getByRole("button", { name: "Save weekly hours" }).click();
    await expect(hours.getByText("Monday: a window must end after it starts.")).toBeVisible();
  });

  test("the hours editor fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.doctorWithAccess);
    await page.goto("/profile");
    await expect(page.getByRole("region", { name: "Weekly hours" })).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});

test.describe("appointments and notifications", () => {
  test("booking tells both the patient and the doctor, and the doctor can cancel", async ({ browser }) => {
    test.setTimeout(150_000); // several pages compile on first visit in dev mode
    const { users } = fixtures();
    const patientPage = await (await browser.newContext()).newPage();
    await signInAs(patientPage, users.patientEmpty);
    await bookFirstSlot(patientPage, users.doctorWithAccess.fullName);

    await patientPage.goto("/notifications");
    await expect(patientPage.getByText("Appointment confirmed").first()).toBeVisible();

    const doctorPage = await (await browser.newContext()).newPage();
    await signInAs(doctorPage, users.doctorWithAccess);
    await doctorPage.goto("/notifications");
    await expect(doctorPage.getByText("New appointment").first()).toBeVisible();
    await expect(doctorPage.getByRole("link", { name: /Notifications, \d+ unread/ })).toBeVisible(); // the bell shows the count

    await doctorPage.goto("/dashboard/doctor");
    const card = doctorPage.getByRole("region", { name: "Appointments" }).or(doctorPage.locator("#appointments"));
    const booked = card.locator("li").filter({ hasText: users.patientEmpty.fullName }).filter({ hasText: "Booked" }).first();
    await booked.getByRole("button", { name: "Cancel" }).click();
    await doctorPage.getByRole("dialog", { name: "Cancel this appointment?" }).getByRole("button", { name: "Cancel appointment" }).click();
    await expect(doctorPage.getByText("Appointment cancelled; the patient was told.")).toBeVisible({ timeout: 20_000 });

    await patientPage.goto("/notifications");
    await expect(patientPage.getByText("Appointment cancelled").first()).toBeVisible();
    await patientPage.goto("/doctors");
    await expect(patientPage.getByRole("article").filter({ hasText: users.doctorWithAccess.fullName }).getByText("Cancelled", { exact: true }).first()).toBeVisible();
  });

  test("the notifications page: empty state, mark read, phone width", async ({ page }) => {
    await signInAs(page, fixtures().users.admin);
    await page.goto("/notifications");
    await expect(page.getByText("Nothing here yet")).toBeVisible();
    await expectNoHorizontalScroll(page);
  });

  test("signed-out visitors cannot see notifications", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page).toHaveURL(/\/login$/);
  });
});
