import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { BASE_URL, fixtures } from "./support/fixtures-file";
import { expectNoHorizontalScroll, signInAs } from "./support/session";

// The browser's location is mocked: granted with a known place and accuracy, or left blocked.
const F10 = { latitude: 33.6940, longitude: 73.0130, accuracy: 120 };

async function grantLocation(context: BrowserContext) {
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation(F10);
}

/** What a doctor's own browser would do, with the doctor's token (the page under test is the patient's). */
async function doctorCall(path: string, body: unknown = {}) {
  const { users } = fixtures();
  const response = await fetch(`${BASE_URL}/api/backend/home-visits${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${users.doctorHomeVisit.token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  expect(response.ok, `${path} -> ${response.status}`).toBeTruthy();
  return response.json();
}

async function doctorOfferId(): Promise<number> {
  const { users } = fixtures();
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const response = await fetch(`${BASE_URL}/api/backend/home-visits/doctor/offers`, {
      headers: { Authorization: `Bearer ${users.doctorHomeVisit.token}` },
    });
    const offers = (await response.json()) as Array<{ id: number }>;
    if (offers.length) return offers[0].id;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("the doctor was never offered the request");
}

async function answerAllNo(page: Page) {
  const no = page.getByRole("radio", { name: "No", exact: true });
  const count = await no.count();
  expect(count).toBeGreaterThanOrEqual(10);
  for (let i = 0; i < count; i += 1) await no.nth(i).check();
}

async function fillRequest(page: Page, reason = "mild fever and a cold for two days") {
  await page.getByLabel("What is the problem?").fill(reason);
  await answerAllNo(page);
  await page.getByLabel("Phone number").fill("0300 1234567");
  await page.getByLabel("Your address in words").fill("House 12, Street 4, F-10/2, Islamabad");
}

test.describe("home visits: the patient's page", () => {
  test("signed out, the page shows the 1122 notice and asks to sign in", async ({ page }) => {
    await page.goto("/emergency");
    await expect(page.getByRole("heading", { name: "Ask for a doctor at home" })).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: "call 1122" })).toBeVisible();
    await expect(page.getByText("Sign in to ask for a home visit")).toBeVisible();
    await expect(page.getByLabel("What is the problem?")).toHaveCount(0);
  });

  test("a doctor account is told to use the dashboard", async ({ page }) => {
    await signInAs(page, fixtures().users.doctor);
    await page.goto("/emergency");
    await expect(page.getByText("Only patient accounts can ask for a home visit.")).toBeVisible({ timeout: 30_000 });
  });

  test("a 'yes' to a safety question shows the 1122 notice and stops the request", async ({ page }) => {
    await signInAs(page, fixtures().users.patientHomeA);
    await page.goto("/emergency");
    await expect(page.getByLabel("What is the problem?")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("radio", { name: "Yes", exact: true }).first().check();
    await expect(page.getByRole("alert").filter({ hasText: "This may be an emergency" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Send request" })).toBeDisabled();
  });

  test("a warning sign in the reason shows only the 1122 notice and saves nothing", async ({ page }) => {
    await grantLocation(page.context());
    await signInAs(page, fixtures().users.patientHomeA);
    await page.goto("/emergency");
    await expect(page.getByLabel("What is the problem?")).toBeVisible({ timeout: 30_000 });
    await fillRequest(page, "I have chest pain since this morning");
    await page.getByRole("button", { name: "Use my current location" }).click();
    await expect(page.getByText(/Location found, accurate to about 120 m/)).toBeVisible();
    await page.getByRole("button", { name: "Send request" }).click();
    const stop = page.getByRole("alert").filter({ hasText: "This may be an emergency" });
    await expect(stop).toBeVisible();
    await expect(stop.getByText("Call 1122 or go to the nearest emergency department.")).toBeVisible();
    await expect(stop.getByText("Nothing was saved and no doctor was contacted.")).toBeVisible();
    await expect(page.getByRole("button", { name: /Send request|Find a doctor/ })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Earlier requests" })).toHaveCount(0);
    await stop.getByRole("button", { name: "Start over" }).click();
    await expect(page.getByLabel("What is the problem?")).toBeVisible();
  });

  test("a problem better seen in a clinic points to booking an appointment", async ({ page }) => {
    await grantLocation(page.context());
    await signInAs(page, fixtures().users.patientHomeA);
    await page.goto("/emergency");
    await expect(page.getByLabel("What is the problem?")).toBeVisible({ timeout: 30_000 });
    await fillRequest(page, "my knee joint pain and swelling after walking");
    await page.getByRole("button", { name: "Use my current location" }).click();
    await expect(page.getByText(/Location found/)).toBeVisible();
    await page.getByRole("button", { name: "Send request" }).click();
    await expect(page.getByRole("heading", { name: "Better seen in a clinic" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Find a doctor and book" })).toHaveAttribute("href", "/doctors");
  });

  test("location: the numbers used are shown, a rough place is flagged, and it can be updated or cleared", async ({ page }) => {
    const context = page.context();
    await context.grantPermissions(["geolocation"]);
    await context.setGeolocation({ latitude: 33.6938, longitude: 73.0129, accuracy: 5000 });
    await signInAs(page, fixtures().users.patientHomeA);
    await page.goto("/emergency");
    await expect(page.getByLabel("What is the problem?")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "Use my current location" }).click();
    await expect(page.getByText("Location found, accurate to about 5.0 km.")).toBeVisible();
    await expect(page.getByText("Coordinates used: 33.69380, 73.01290")).toBeVisible();
    await expect(page.getByText(/only approximate/)).toBeVisible();

    await context.setGeolocation({ latitude: 33.71, longitude: 73.055, accuracy: 30 });
    await page.getByRole("button", { name: "Update my location" }).click();
    await expect(page.getByText("Coordinates used: 33.71000, 73.05500")).toBeVisible();
    await expect(page.getByText("Location found, accurate to about 30 m.")).toBeVisible();
    await expect(page.getByText(/only approximate/)).toHaveCount(0);

    await page.getByRole("button", { name: "Clear location" }).click();
    await expect(page.getByText("A location is needed before a request can be sent.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Use my current location" })).toBeVisible();
  });

  test("location: blocked shows a plain message and typed coordinates, with a range check", async ({ page }) => {
    await signInAs(page, fixtures().users.patientHomeA);
    await page.goto("/emergency");
    await expect(page.getByLabel("What is the problem?")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "Use my current location" }).click();
    await expect(page.getByText(/Location access is blocked for this site/)).toBeVisible();
    await page.getByLabel("Latitude").fill("95");
    await page.getByLabel("Longitude").fill("73.01");
    await page.getByRole("button", { name: "Use these numbers" }).click();
    await expect(page.getByText("Latitude must be between -90 and 90.")).toBeVisible();
    await page.getByLabel("Latitude").fill("33.6938");
    await page.getByRole("button", { name: "Use these numbers" }).click();
    await expect(page.getByText("Location typed by you.")).toBeVisible();
    // Without a location a request cannot be sent: after typing it and clearing nothing else, the form still asks for the rest.
    await page.getByRole("button", { name: "Send request" }).click();
    await expect(page.getByText("Describe the problem in a few words.")).toBeVisible();
  });

  test("a request cannot be sent without a location", async ({ page }) => {
    await signInAs(page, fixtures().users.patientHomeA);
    await page.goto("/emergency");
    await expect(page.getByLabel("What is the problem?")).toBeVisible({ timeout: 30_000 });
    await fillRequest(page);
    await page.getByRole("button", { name: "Send request" }).click();
    await expect(page.getByText("Add your location first.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Your home visit" })).toHaveCount(0);
  });

  test("an automatic request is tracked from offer to a saved summary, with the doctor's own estimate", async ({ page }) => {
    await grantLocation(page.context());
    await signInAs(page, fixtures().users.patientHomeB);
    await page.goto("/emergency");
    await expect(page.getByLabel("What is the problem?")).toBeVisible({ timeout: 30_000 });
    await fillRequest(page);
    await page.getByRole("button", { name: "Use my current location" }).click();
    await expect(page.getByText(/Location found/)).toBeVisible();
    await page.getByRole("button", { name: "Send request" }).click();

    const tracker = page.getByRole("region", { name: "Your home visit" });
    await expect(tracker.getByText("Waiting for a doctor to accept")).toBeVisible({ timeout: 30_000 });
    await expect(tracker.getByText(/Asking doctor 1 of up to 5/)).toBeVisible();
    await expect(tracker.getByRole("button", { name: "Cancel this visit" })).toBeVisible();
    // The form is gone while a visit is live, and no map or live position is shown.
    await expect(page.getByLabel("What is the problem?")).toHaveCount(0);
    await expect(page.locator("iframe, canvas, img[src*='map']")).toHaveCount(0);

    const id = await doctorOfferId();
    await doctorCall(`/${id}/accept`);
    await expect(tracker.getByText("Doctor accepted", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
    await expect(tracker.getByText(fixtures().users.doctorHomeVisit.fullName)).toBeVisible();

    await doctorCall(`/${id}/en-route`, { eta_minutes: 20 });
    await expect(tracker.getByText(/Doctor's estimate: about 20 minutes/)).toBeVisible({ timeout: 30_000 });
    await expect(tracker.getByText(/not a tracked arrival time/)).toBeVisible();
    await expect(tracker.getByRole("button", { name: "Cancel this visit" })).toBeVisible();

    await doctorCall(`/${id}/arrived`);
    await expect(tracker.getByText("Doctor has arrived").first()).toBeVisible({ timeout: 30_000 });
    await expect(tracker.getByRole("button", { name: "Cancel this visit" })).toHaveCount(0);

    await doctorCall(`/${id}/complete`);
    await doctorCall(`/${id}/close`, { findings: "Mild viral fever", advice: "Rest and fluids", follow_up: "Clinic visit if the fever lasts 3 days" });
    const history = page.getByRole("region", { name: "Earlier requests" });
    await expect(history.getByText("Visit closed and saved to the record")).toBeVisible({ timeout: 30_000 });
    await expect(history.getByText("Mild viral fever")).toBeVisible();
    await expect(history.getByText("Rest and fluids")).toBeVisible();
    await expect(history.getByText("Clinic visit if the fever lasts 3 days")).toBeVisible();
    // The live visit is over, so the form is back for a new request.
    await expect(page.getByLabel("What is the problem?")).toBeVisible();
  });

  test("choosing a doctor lists them with a straight-line distance; the request can be cancelled", async ({ page }) => {
    await grantLocation(page.context());
    await signInAs(page, fixtures().users.patientHomeC);
    await page.goto("/emergency");
    await expect(page.getByLabel("What is the problem?")).toBeVisible({ timeout: 30_000 });
    await fillRequest(page);
    await page.getByRole("radio", { name: /I will choose a doctor/ }).check();
    await page.getByRole("button", { name: "Use my current location" }).click();
    await expect(page.getByText(/Location found/)).toBeVisible();
    await page.getByRole("button", { name: "Find doctors near me" }).click();

    const list = page.getByRole("region", { name: "Doctors near you" });
    await expect(list.getByText(fixtures().users.doctorHomeVisit.fullName)).toBeVisible({ timeout: 30_000 });
    await expect(list.getByText(/straight-line distance, (about|less than)/)).toBeVisible();
    await expect(list.getByText("Available now")).toBeVisible();
    await expect(list.getByText(/road|minutes away|ETA/i)).toHaveCount(0);
    await list.getByRole("button", { name: /^Send the request to / }).click();

    const tracker = page.getByRole("region", { name: "Your home visit" });
    await expect(tracker.getByText(/Waiting for .* to answer. They have 10 minutes./)).toBeVisible({ timeout: 30_000 });
    await tracker.getByRole("button", { name: "Cancel this visit" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Cancel the visit" }).click();
    const history = page.getByRole("region", { name: "Earlier requests" });
    await expect(history.getByText("Cancelled")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByLabel("What is the problem?")).toBeVisible();
  });

  test("the doctor referring to emergency care shows the 1122 notice to the patient", async ({ page }) => {
    await grantLocation(page.context());
    await signInAs(page, fixtures().users.patientHomeA);
    await page.goto("/emergency");
    await expect(page.getByLabel("What is the problem?")).toBeVisible({ timeout: 30_000 });
    await fillRequest(page);
    await page.getByRole("button", { name: "Use my current location" }).click();
    await expect(page.getByText(/Location found/)).toBeVisible();
    await page.getByRole("button", { name: "Send request" }).click();
    await expect(page.getByRole("region", { name: "Your home visit" })).toBeVisible({ timeout: 30_000 });
    const id = await doctorOfferId();
    await doctorCall(`/${id}/escalate`);
    const history = page.getByRole("region", { name: "Earlier requests" });
    await expect(history.getByRole("alert").filter({ hasText: "Call 1122 or go to the nearest emergency department." })).toBeVisible({ timeout: 30_000 });
    await expect(history.getByText("Referred to emergency care")).toBeVisible();
  });

  test("the request form fits a phone screen @mobile", async ({ page }) => {
    await signInAs(page, fixtures().users.patientHomeA);
    await page.goto("/emergency");
    await expect(page.getByLabel("What is the problem?")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "Use my current location" }).click();
    await expect(page.getByLabel("Latitude")).toBeVisible();
    await expectNoHorizontalScroll(page);
  });
});
