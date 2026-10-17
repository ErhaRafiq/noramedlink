import { expect, test } from "@playwright/test";

import { BASE_URL, fixtures } from "./support/fixtures-file";
import { ACCESS_COOKIE, REFRESH_COOKIE, alertWithText, loginThroughForm, signInAs } from "./support/session";

// Sign-in and refresh calls are limited per client IP. The whole suite runs from one machine, so late in a long
// run these tests could meet a limit that earlier specs used up. The Next.js proxy forwards the browser's
// X-Forwarded-For, so this file counts as its own client (a documentation address, never a real one).
test.use({ extraHTTPHeaders: { "x-forwarded-for": "198.51.100.41" } });

test.describe("sign in", () => {
  test("asks for both fields before calling the API", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(alertWithText(page, "Enter your email and password.")).toBeVisible();
  });

  test("shows the API's message for a wrong password", async ({ page }) => {
    await loginThroughForm(page, fixtures().users.patientEmpty.email, "not-the-password");
    await expect(alertWithText(page, "Invalid email or password.")).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  for (const [key, path] of [
    ["patient", /\/dashboard\/patient$/],
    ["doctor", /\/dashboard\/doctor$/],
    ["admin", /\/admin$/],
  ] as const) {
    test(`a ${key} lands on their own dashboard`, async ({ page }) => {
      await loginThroughForm(page, fixtures().users[key].email);
      await expect(page).toHaveURL(path);
    });
  }
});

test.describe("protected pages", () => {
  test("without a session they send you to sign in", async ({ page }) => {
    for (const path of ["/dashboard/patient", "/dashboard/doctor", "/admin"]) {
      await page.goto(path);
      await expect(page).toHaveURL(/\/login$/);
    }
  });

  test("the wrong role is sent to its own dashboard", async ({ page }) => {
    await signInAs(page, fixtures().users.patient);
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/dashboard\/patient$/);
    await page.goto("/dashboard/doctor");
    await expect(page).toHaveURL(/\/dashboard\/patient$/);
  });

  test("a revoked or invalid session cookie signs you out", async ({ page }) => {
    await page.context().addCookies([{ name: ACCESS_COOKIE, value: "not-a-valid-token", url: BASE_URL, httpOnly: true, sameSite: "Lax" }]);
    await page.addInitScript(() => {
      localStorage.setItem("nora_medlink_user", JSON.stringify({ id: 1, role: "patient", full_name: "Someone" }));
    });
    await page.goto("/dashboard/patient");
    await expect(page).toHaveURL(/\/login$/);
    expect(await page.evaluate(() => localStorage.getItem("nora_medlink_user"))).toBeNull();
  });
});

test.describe("old URLs and unknown pages", () => {
  test("/dashboard and /doctor-dashboard redirect to the new dashboards", async ({ request }) => {
    for (const [from, to] of [
      ["/dashboard", "/dashboard/patient"],
      ["/doctor-dashboard", "/dashboard/doctor"],
    ]) {
      const response = await request.get(from, { maxRedirects: 0 });
      expect(response.status()).toBe(307);
      expect(response.headers().location).toBe(to);
    }
  });

  test("an unknown page shows the not-found page", async ({ page }) => {
    const response = await page.goto("/no-such-page");
    expect(response?.status()).toBe(404);
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  });
});

test.describe("the session is a cookie JavaScript cannot read", () => {
  test("login sets HttpOnly cookies and the page never sees a token", async ({ page }) => {
    await loginThroughForm(page, fixtures().users.patientEmpty.email);
    await expect(page).toHaveURL(/\/dashboard\/patient$/);

    const cookies = await page.context().cookies();
    for (const name of [ACCESS_COOKIE, REFRESH_COOKIE]) {
      const cookie = cookies.find((c) => c.name === name);
      expect(cookie?.httpOnly, `${name} is HttpOnly`).toBe(true);
      expect(cookie?.sameSite, `${name} is SameSite`).not.toBe("None");
    }
    const visibleToScripts = await page.evaluate(() => ({
      cookie: document.cookie,
      storage: JSON.stringify({ ...localStorage }),
    }));
    expect(visibleToScripts.cookie).not.toContain("nora_");
    expect(visibleToScripts.storage).not.toMatch(/eyJ|access_token|refresh_token/); // no JWT anywhere in storage
  });

  test("an expired access token is renewed from the refresh cookie without signing in again", async ({ page }) => {
    await loginThroughForm(page, fixtures().users.admin.email);
    await expect(page).toHaveURL(/\/admin$/);
    const before = (await page.context().cookies()).find((c) => c.name === REFRESH_COOKIE)?.value;

    await page.context().clearCookies({ name: ACCESS_COOKIE }); // as if the 15-minute access token had expired
    await page.reload();
    // Wait for the outcome itself, not for "a" session check: a call still in flight from the page before the
    // reload would answer first and be read as the renewed session (it has no new cookies yet).
    await expect(page.getByRole("heading", { name: "Admin dashboard" })).toBeVisible();
    await expect
      .poll(async () => (await page.context().cookies()).find((c) => c.name === ACCESS_COOKIE)?.httpOnly, {
        message: "the proxy refreshed the session and set a new access cookie",
      })
      .toBe(true);
    await expect
      .poll(async () => {
        const after = (await page.context().cookies()).find((c) => c.name === REFRESH_COOKIE)?.value;
        return Boolean(after && after !== before);
      }, { message: "the refresh token was rotated" })
      .toBe(true);
    await expect(page).toHaveURL(/\/admin$/); // still signed in
  });

  test("signing out ends the session on the server: the old refresh cookie no longer works", async ({ page, request }) => {
    await loginThroughForm(page, fixtures().users.doctorWithAccess.email);
    await expect(page).toHaveURL(/\/dashboard\/doctor$/);
    const refresh = (await page.context().cookies()).find((c) => c.name === REFRESH_COOKIE)?.value ?? "";

    await page.getByRole("button", { name: "Sign out" }).first().click();
    await expect(page).toHaveURL(/\/login$/);
    expect((await page.context().cookies()).filter((c) => c.name.startsWith("nora_"))).toHaveLength(0);

    // Replaying the old refresh token (as a thief with a copy would) gets nothing.
    const replay = await request.get(`${BASE_URL}/api/backend/api/auth/me`, { headers: { Cookie: `${REFRESH_COOKIE}=${refresh}` } });
    expect(replay.status()).toBe(401);
  });

  test("the token endpoints are not reachable through the API proxy, and cross-site posts are refused", async ({ request }) => {
    const login = await request.post(`${BASE_URL}/api/backend/auth/login`, { data: { email: "x@example.com", password: "x" } });
    expect(login.status()).toBe(404); // sign-in only exists at /api/auth/login, which sets cookies instead
    const forged = await request.post(`${BASE_URL}/api/backend/appointments`, {
      headers: { Origin: "https://evil.example" },
      data: {},
    });
    expect(forged.status()).toBe(403);
  });
});
