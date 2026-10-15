import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { alertWithText, expectNoHorizontalScroll, signInAs } from "./support/session";

test.describe("consultation payments", () => {
  test("the doctor sets a fee, and the patient's appointment can be paid at that fee", async ({ browser }) => {
    const { users, stripeKeySet } = fixtures();
    test.skip(stripeKeySet, "would open Stripe's payment page (run with DISABLE_PAID_SERVICES=1)");

    const doctorPage = await (await browser.newContext()).newPage();
    await signInAs(doctorPage, users.doctor);
    await doctorPage.goto("/dashboard/doctor");
    const feeCard = doctorPage.getByRole("region", { name: "Consultation fee" });
    await feeCard.getByLabel("Fee (PKR)").fill("1500");
    await feeCard.getByRole("button", { name: "Save fee" }).click();
    await expect(feeCard.getByText("Fee saved")).toBeVisible({ timeout: 20_000 });
    await expect(feeCard.getByText("Patients pay PKR 1,500 online")).toBeVisible();

    const page = await (await browser.newContext()).newPage();
    await signInAs(page, users.patientEmpty);
    await page.goto("/doctors");
    await page.getByRole("searchbox", { name: "Search doctors" }).fill(users.doctor.fullName);
    const card = page.getByRole("article").filter({ hasText: users.doctor.fullName }).filter({ has: page.getByRole("button", { name: "Book appointment" }) });
    await expect(card.getByText("PKR 1,500 per consultation")).toBeVisible();
    await card.getByRole("button", { name: "Book appointment" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Appointment booked" }).first()).toBeVisible({ timeout: 20_000 });

    await page.getByRole("link", { name: "Pay PKR 1,500" }).first().click();
    await expect(page.getByRole("heading", { name: "Consultation payments" })).toBeVisible();
    const toPay = page.getByRole("region", { name: "Appointments to pay" });
    await toPay.getByRole("button", { name: "Pay PKR 1,500" }).first().click();
    // Stripe is off in test runs: the server refuses instead of opening the payment page.
    await expect(alertWithText(page, "Online payment is not set up")).toBeVisible({ timeout: 20_000 });
    await expect(page).toHaveURL(/\/payments/);
    await expectNoHorizontalScroll(page);
  });

  test("the result page without a Stripe session says so", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/payments/result");
    await expect(page.getByText("This link has no payment session.")).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});
