import { expect, type Page } from "@playwright/test";

import { BASE_URL, fixtures, type TestUser } from "./fixtures-file";

/**
 * Signs `user` in the way the app does after login (token + user in localStorage), without
 * going through the login form. Used by every test except the login tests themselves, so
 * the suite stays well under the login rate limits.
 */
export async function signInAs(page: Page, user: TestUser) {
  const response = await fetch(`${BASE_URL}/api/backend/api/auth/me`, { headers: { Authorization: `Bearer ${user.token}` } });
  expect(response.ok, `/auth/me for ${user.email}`).toBeTruthy();
  const me = await response.json();
  await page.addInitScript(
    ([token, userJson]) => {
      localStorage.setItem("nora_medlink_token", token);
      localStorage.setItem("nora_medlink_user", userJson);
    },
    [user.token, JSON.stringify(me)] as const,
  );
}

/** Signs in through the real login form. */
export async function loginThroughForm(page: Page, email: string, password = fixtures().password) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** An error or status message with this text. Next.js also renders an empty role="alert" route announcer. */
export function alertWithText(page: Page, text: string | RegExp) {
  return page.getByRole("alert").filter({ hasText: text });
}

/** Fails if the page scrolls sideways (the phone-width rule in AGENTS.md section 15). */
export async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "page is wider than the viewport").toBeLessThanOrEqual(1);
}
