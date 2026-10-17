import { expect, test } from "@playwright/test";

import { fixtures } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

test.describe("PMDC number at signup", () => {
  test("a number that is not in the PMDC form is explained before anything is sent", async ({ page }) => {
    await page.goto("/signup?role=doctor");
    const number = page.getByLabel("PMDC/PMC registration number");
    await expect(number).toHaveAttribute("placeholder", "12345-P");

    await number.fill("PMC-00000");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText(/That number is not in a recognised form\. Enter the number as printed on your PMDC certificate/)).toBeVisible();

    await number.fill("pmdc 12345 p"); // an accepted way of writing it: the error goes away
    await expect(page.getByText(/That number is not in a recognised form/)).toHaveCount(0);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText(/That number is not in a recognised form/)).toHaveCount(0); // other fields are still empty
  });

  test("the signup form fits a phone screen with the PMDC hint @mobile", async ({ page }) => {
    await page.goto("/signup?role=doctor");
    await expect(page.getByText(/An administrator checks it on the PMDC register/)).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});

test.describe("PMDC verification (admin)", () => {
  test("the admin decides by hand, patients see the badge and can filter by it, and the doctor sees their status", async ({ browser }) => {
    const { users } = fixtures();
    const doctor = users.doctor;

    const adminContext = await browser.newContext();
    const admin = await adminContext.newPage();
    await signInAs(admin, users.admin);
    await admin.goto("/admin");
    const section = admin.locator("#all-doctors");
    await expect(section.getByRole("heading", { name: "All doctors and PMDC verification" })).toBeVisible({ timeout: 30_000 });
    await section.getByLabel("Name or number").fill(doctor.fullName);
    const row = section.getByRole("listitem").filter({ hasText: doctor.fullName });
    await expect(row).toBeVisible();

    // The fixture's number is a placeholder: the register cannot search it, so a check is not offered.
    const panel = row.getByLabel("PMDC verification");
    await expect(panel.getByText("Number not recognised")).toBeVisible();
    await expect(panel.getByRole("button", { name: "Check on PMDC" })).toBeDisabled();
    await expect(panel.getByRole("link", { name: /Open the PMDC register/ })).toHaveAttribute("href", "https://pmdc.pk/");

    await panel.getByRole("button", { name: "Decide by hand" }).click();
    const dialog = admin.getByRole("dialog", { name: "Decide PMDC verification by hand" });
    const save = dialog.getByRole("button", { name: "Save decision" });
    await expect(save).toBeDisabled(); // a reason is required
    await dialog.getByLabel("Reason").fill("too short");
    await expect(save).toBeDisabled();
    await dialog.getByLabel("Reason").fill("Checked on pmdc.pk: the name is spelled differently.");
    await dialog.getByRole("radio", { name: /^PMDC verified/ }).check();
    await save.click();
    await expect(dialog).toBeHidden();
    await expect(panel.getByText("PMDC verified", { exact: true })).toBeVisible();
    await expect(panel.getByText(/An administrator decided by hand: Checked on pmdc\.pk/)).toBeVisible();

    // The filter on the admin list.
    await section.getByLabel("PMDC", { exact: true }).selectOption("verified");
    await expect(section.getByRole("listitem").filter({ hasText: doctor.fullName })).toBeVisible();
    await section.getByLabel("PMDC", { exact: true }).selectOption("unverified");
    await expect(section.getByRole("listitem").filter({ hasText: doctor.fullName })).toHaveCount(0);

    // Patients: the badge on the card, and the filter.
    const visitor = await (await browser.newContext()).newPage();
    await visitor.goto("/doctors");
    await visitor.getByRole("searchbox", { name: "Search doctors" }).fill(doctor.fullName);
    const card = visitor.getByRole("article").filter({ hasText: doctor.fullName });
    await expect(card.getByText("PMDC verified")).toBeVisible();
    await visitor.getByRole("searchbox", { name: "Search doctors" }).fill("");
    await visitor.getByLabel("PMDC verified only").check();
    await expect(visitor.getByRole("article").filter({ hasText: doctor.fullName })).toBeVisible();
    await expect(visitor.getByRole("article").filter({ hasText: users.doctorWithAccess.fullName })).toHaveCount(0);

    // The doctor's own profile says where it stands.
    const own = await (await browser.newContext()).newPage();
    await signInAs(own, doctor);
    await own.goto("/profile");
    await expect(own.getByTestId("pmdc-status").getByText("PMDC verified")).toBeVisible({ timeout: 30_000 });

    // Taking the badge away.
    await admin.getByRole("button", { name: "Clear filters" }).click();
    await section.getByLabel("Name or number").fill(doctor.fullName);
    await panel.getByRole("button", { name: "Decide by hand" }).click();
    await dialog.getByRole("radio", { name: /^Not PMDC verified/ }).check();
    await dialog.getByLabel("Reason").fill("Withdrawn while the register is rechecked.");
    await save.click();
    await expect(dialog).toBeHidden();
    await visitor.reload();
    await visitor.getByRole("searchbox", { name: "Search doctors" }).fill(doctor.fullName);
    await expect(visitor.getByRole("article").filter({ hasText: doctor.fullName }).getByText("PMDC verified")).toHaveCount(0);
    await adminContext.close();
  });

  test("a pending doctor's PMDC panel is part of the review queue, and approval does not need it", async ({ page }) => {
    const doctor = fixtures().users.doctorUnreviewed; // pending, and no other spec approves or rejects it
    await signInAs(page, fixtures().users.admin);
    await page.goto("/admin");
    const row = page.locator("#doctors").getByRole("listitem").filter({ hasText: doctor.fullName });
    await expect(row.getByLabel("PMDC verification")).toBeVisible({ timeout: 30_000 });
    await expect(row.getByLabel("PMDC verification").getByRole("button", { name: "Decide by hand" })).toBeVisible();
    await expect(row.getByRole("button", { name: "Approve" })).toBeEnabled(); // no PMDC check is required
  });

  test("the admin's PMDC panel fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.admin);
    await page.goto("/admin");
    await expect(page.locator("#all-doctors").getByRole("heading", { name: "All doctors and PMDC verification" })).toBeVisible({ timeout: 30_000 });
    await expectNoHorizontalScroll(page);
  });

  test("a patient cannot see the admin PMDC tools", async ({ page }) => {
    await signInAs(page, fixtures().users.patientEmpty);
    await page.goto("/admin");
    await expect(page).not.toHaveURL(/\/admin$/);
  });
});
