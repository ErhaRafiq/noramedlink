import { expect, test } from "@playwright/test";

import { BASE_URL, fixtures, type TestUser } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

const F10 = { latitude: 33.694, longitude: 73.013, accuracy: 120 };
const PHONE = "0300 7654321";
const ADDRESS = "House 7, Street 9, F-10/3, Islamabad";

/** A patient's request, sent the way the patient's page does (their token, the checklist all "no"). */
async function patientRequests(patient: TestUser) {
  const response = await fetch(`${BASE_URL}/api/backend/home-visits/requests`, {
    method: "POST",
    headers: { Authorization: `Bearer ${patient.token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      reason: "mild fever and a cold for two days",
      checklist: Object.fromEntries(Array.from({ length: 11 }, (_, i) => [`HC-${String(i + 1).padStart(2, "0")}`, false])),
      location: { latitude: 33.694, longitude: 73.013, accuracy_m: 120, source: "device" },
      mode: "auto",
      phone: PHONE,
      address_text: ADDRESS,
    }),
  });
  expect(response.status, "the request was created").toBe(201);
  return ((await response.json()) as { visit: { id: number } }).visit.id;
}

async function patientVisit(patient: TestUser, id: number) {
  const response = await fetch(`${BASE_URL}/api/backend/home-visits/${id}`, { headers: { Authorization: `Bearer ${patient.token}` } });
  return (await response.json()) as { status: string; summary: { advice: string } | null; emergency_notice: string | null };
}

test.describe("home visits: the doctor's side", () => {
  test("a doctor sets the switch, radius and base location in the profile", async ({ page }) => {
    const context = page.context();
    await context.grantPermissions(["geolocation"]);
    await context.setGeolocation(F10);
    await signInAs(page, fixtures().users.doctorHomeSetup);
    await page.goto("/profile");
    const form = page.getByRole("form", { name: "Home-visit settings" });
    await expect(form).toBeVisible({ timeout: 30_000 });

    // Nothing is invented: no base is saved yet, and switching on without one is refused.
    await expect(form.getByText("No base location is saved yet.")).toBeVisible();
    await form.getByLabel("I take home visits").check();
    await form.getByLabel("Service radius (km)").fill("10");
    await form.getByRole("button", { name: "Save home-visit settings" }).click();
    await expect(form.getByText("Set your base location and service radius before switching home visits on.")).toBeVisible();

    await form.getByLabel("Service radius (km)").fill("80");
    await form.getByRole("button", { name: "Save home-visit settings" }).click();
    await expect(form.getByText("The service radius must be between 1 and 50 km.")).toBeVisible();
    await form.getByLabel("Service radius (km)").fill("10");

    await form.getByRole("button", { name: "Use my current location" }).click();
    await expect(form.getByText("Coordinates used: 33.69400, 73.01300")).toBeVisible();
    await form.getByRole("button", { name: "Save home-visit settings" }).click();
    await expect(form.getByText("Home-visit settings saved.")).toBeVisible();

    await page.reload();
    const again = page.getByRole("form", { name: "Home-visit settings" });
    await expect(again.getByText("Saved base: 33.69400, 73.01300")).toBeVisible({ timeout: 30_000 });
    await expect(again.getByLabel("I take home visits")).toBeChecked();
    await expect(again.getByLabel("Service radius (km)")).toHaveValue("10");

    // Typed numbers work too, and a bad latitude is explained.
    await again.getByRole("button", { name: "Type latitude and longitude instead" }).click();
    await again.getByLabel("Latitude").fill("95");
    await again.getByLabel("Longitude").fill("73");
    await again.getByRole("button", { name: "Use these numbers" }).click();
    await expect(again.getByText("Latitude must be between -90 and 90.")).toBeVisible();

    // Switching off keeps the saved base.
    await again.getByLabel("I take home visits").uncheck();
    await again.getByRole("button", { name: "Save home-visit settings" }).click();
    await expect(again.getByText("Home-visit settings saved.")).toBeVisible();
    await expect(again.getByText("Saved base: 33.69400, 73.01300")).toBeVisible();
  });

  test("with nothing waiting, the card says so and links to the settings", async ({ page }) => {
    await signInAs(page, fixtures().users.doctorHomeSetup);
    await page.goto("/dashboard/doctor");
    const card = page.locator("#home-visits");
    await expect(card.getByRole("heading", { name: "Home visits" })).toBeVisible({ timeout: 30_000 });
    await expect(card.getByText("No home visit requests right now")).toBeVisible();
    await expect(card.getByRole("link", { name: "Home-visit settings" })).toHaveAttribute("href", "/profile#home-visits");
  });

  test("a doctor accepts a request, sees the patient's contact, takes every step and closes it with a summary", async ({ page }) => {
    const { users } = fixtures();
    const id = await patientRequests(users.patientHomeD);
    await signInAs(page, users.doctorHomeVisit);
    await page.goto("/dashboard/doctor");
    const card = page.locator("#home-visits");
    const offer = card.getByRole("article", { name: "Home visit request waiting for you" });
    await expect(offer).toBeVisible({ timeout: 30_000 });
    // Before accepting: the reason and a rounded straight-line distance, but no name, phone or address.
    await expect(offer.getByText("mild fever and a cold for two days")).toBeVisible();
    await expect(offer.getByText(/straight-line distance/)).toBeVisible();
    await expect(offer.getByRole("timer", { name: "Time left to answer" })).toContainText("Answer within");
    await expect(card.getByText(PHONE)).toHaveCount(0);
    await expect(card.getByText(ADDRESS)).toHaveCount(0);
    await expect(card.getByText(users.patientHomeD.fullName)).toHaveCount(0);

    await offer.getByRole("button", { name: "Accept" }).click();
    const visit = card.getByRole("article", { name: `Home visit with ${users.patientHomeD.fullName}` });
    await expect(visit).toBeVisible({ timeout: 30_000 });
    await expect(visit.getByRole("link", { name: PHONE })).toHaveAttribute("href", "tel:03007654321");
    await expect(visit.getByText(ADDRESS)).toBeVisible();
    await expect(visit.getByText(/Straight-line only, not a route/)).toBeVisible();
    expect((await patientVisit(users.patientHomeD, id)).status).toBe("accepted");

    await visit.getByLabel("Your estimate in minutes (optional)").fill("500");
    await expect(visit.getByText("Enter whole minutes, 1 to 240.")).toBeVisible();
    await visit.getByLabel("Your estimate in minutes (optional)").fill("15");
    await visit.getByRole("button", { name: "I am on my way" }).click();
    await expect(visit.getByText("Doctor is on the way").first()).toBeVisible({ timeout: 30_000 });
    await expect(visit.getByText(/Your estimate: about 15 minutes/)).toBeVisible();
    await visit.getByRole("button", { name: "I have arrived" }).click();
    await expect(visit.getByText("Doctor has arrived").first()).toBeVisible({ timeout: 30_000 });
    await visit.getByRole("button", { name: "The visit is finished" }).click();

    const summary = visit.getByRole("form", { name: "Visit summary" });
    await expect(summary).toBeVisible({ timeout: 30_000 });
    await summary.getByRole("button", { name: "Save summary and close" }).click();
    await expect(summary.getByText("Write what you found.")).toBeVisible();
    await summary.getByLabel("What you found").fill("Mild viral fever");
    await summary.getByLabel("Advice given").fill("Rest and plenty of fluids");
    await summary.getByLabel("Follow-up").fill("Clinic visit if the fever lasts 3 days");
    await summary.getByRole("button", { name: "Save summary and close" }).click();

    // The closed visit moves to the past list: the summary stays, the phone and address are gone.
    const past = card.getByRole("region", { name: "Past home visits" });
    await expect(past.getByText("Rest and plenty of fluids")).toBeVisible({ timeout: 30_000 });
    await expect(past.getByText(users.patientHomeD.fullName)).toBeVisible();
    await expect(past.getByText(PHONE)).toHaveCount(0);
    await expect(past.getByText(ADDRESS)).toHaveCount(0);
    expect((await patientVisit(users.patientHomeD, id)).summary?.advice).toBe("Rest and plenty of fluids");
  });

  test("declining ends the request for this doctor and the patient is told nobody was found", async ({ page }) => {
    const { users } = fixtures();
    const id = await patientRequests(users.patientHomeE);
    await signInAs(page, users.doctorHomeVisit);
    await page.goto("/dashboard/doctor");
    const card = page.locator("#home-visits");
    const offer = card.getByRole("article", { name: "Home visit request waiting for you" });
    await expect(offer).toBeVisible({ timeout: 30_000 });
    await offer.getByRole("button", { name: "Decline" }).click();
    await expect(offer).toHaveCount(0, { timeout: 30_000 });
    await expect(card.getByText("No home visit requests right now")).toBeVisible();
    expect((await patientVisit(users.patientHomeE, id)).status).toBe("no_doctor_found");
  });

  test("a doctor can refer to emergency care, and the patient is told to call 1122", async ({ page }) => {
    const { users } = fixtures();
    const id = await patientRequests(users.patientHomeF);
    await signInAs(page, users.doctorHomeVisit);
    await page.goto("/dashboard/doctor");
    const card = page.locator("#home-visits");
    await card.getByRole("article", { name: "Home visit request waiting for you" }).getByRole("button", { name: "Accept" }).click();
    const visit = card.getByRole("article", { name: `Home visit with ${users.patientHomeF.fullName}` });
    await expect(visit).toBeVisible({ timeout: 30_000 });
    await visit.getByRole("button", { name: "This is an emergency" }).click();
    const dialog = page.getByRole("dialog", { name: "Tell the patient to get emergency care?" });
    await dialog.getByRole("button", { name: "Refer to emergency care" }).click();
    const past = card.getByRole("region", { name: "Past home visits" });
    await expect(past.getByText("Referred to emergency care")).toBeVisible({ timeout: 30_000 });
    const patient = await patientVisit(users.patientHomeF, id);
    expect(patient.status).toBe("referred_emergency");
    expect(patient.emergency_notice).toContain("1122");
  });

  test("a doctor who cancels before arriving needs a reason, and the request goes back to matching", async ({ page }) => {
    const { users } = fixtures();
    const id = await patientRequests(users.patientHomeE);
    await signInAs(page, users.doctorHomeVisit);
    await page.goto("/dashboard/doctor");
    const card = page.locator("#home-visits");
    await card.getByRole("article", { name: "Home visit request waiting for you" }).getByRole("button", { name: "Accept" }).click();
    const visit = card.getByRole("article", { name: `Home visit with ${users.patientHomeE.fullName}` });
    await expect(visit).toBeVisible({ timeout: 30_000 });
    await visit.getByRole("button", { name: "Cancel this visit" }).click();
    const dialog = page.getByRole("dialog", { name: "Cancel this home visit?" });
    await expect(dialog.getByText(/sends the request back to matching/)).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Cancel the visit" })).toBeDisabled();
    await dialog.getByLabel("Why are you cancelling?").selectOption("unwell");
    await dialog.getByRole("button", { name: "Cancel the visit" }).click();
    // Back to matching: this doctor no longer holds it and never sees it again; with nobody else eligible it ends.
    await expect(visit).toHaveCount(0, { timeout: 30_000 });
    await expect(card.getByText("No home visit requests right now")).toBeVisible();
    expect((await patientVisit(users.patientHomeE, id)).status).toBe("no_doctor_found");
  });

  test("a doctor who cancels after arriving ends the visit", async ({ page }) => {
    const { users } = fixtures();
    const id = await patientRequests(users.patientHomeD);
    await signInAs(page, users.doctorHomeVisit);
    await page.goto("/dashboard/doctor");
    const card = page.locator("#home-visits");
    await card.getByRole("article", { name: "Home visit request waiting for you" }).getByRole("button", { name: "Accept" }).click();
    const visit = card.getByRole("article", { name: `Home visit with ${users.patientHomeD.fullName}` });
    await expect(visit).toBeVisible({ timeout: 30_000 });
    await visit.getByRole("button", { name: "I am on my way" }).click();
    await expect(visit.getByRole("button", { name: "I have arrived" })).toBeVisible({ timeout: 30_000 });
    await visit.getByRole("button", { name: "I have arrived" }).click();
    await expect(visit.getByRole("button", { name: "The visit is finished" })).toBeVisible({ timeout: 30_000 });
    await visit.getByRole("button", { name: "Cancel this visit" }).click();
    const dialog = page.getByRole("dialog", { name: "Cancel this home visit?" });
    await expect(dialog.getByText(/cancelling ends this visit/)).toBeVisible();
    await dialog.getByLabel("Why are you cancelling?").selectOption("patient_unreachable");
    await dialog.getByRole("button", { name: "Cancel the visit" }).click();
    const past = card.getByRole("region", { name: "Past home visits" });
    await expect(past.getByText("Cancelled", { exact: true })).toBeVisible({ timeout: 30_000 });
    expect((await patientVisit(users.patientHomeD, id)).status).toBe("cancelled");
  });

  test("the doctor's home-visit settings and card fit a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.doctorHomeSetup);
    await page.goto("/profile");
    await expect(page.getByRole("form", { name: "Home-visit settings" })).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "Use my current location" }).click();
    await expect(page.getByLabel("Latitude")).toBeVisible();
    await expectNoHorizontalScroll(page);
    await page.goto("/dashboard/doctor");
    await expect(page.locator("#home-visits").getByRole("heading", { name: "Home visits" })).toBeVisible({ timeout: 30_000 });
    await expectNoHorizontalScroll(page);
  });
});
