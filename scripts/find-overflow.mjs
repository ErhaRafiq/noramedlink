/**
 * Lists elements wider than a phone viewport (horizontal overflow hunting).
 *   node scripts/find-overflow.mjs <url> [tokens.json] [role]
 */
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const [url, tokensFile, role] = process.argv.slice(2);
const browser = await chromium.launch({ channel: "msedge", headless: true });
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
if (tokensFile && role) {
  const token = JSON.parse(readFileSync(tokensFile, "utf8"))[role];
  const base = new URL(url).origin;
  const user = await (await fetch(`${base}/api/backend/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } })).json();
  await context.addInitScript(
    ([t, u]) => {
      localStorage.setItem("nora_medlink_token", t);
      localStorage.setItem("nora_medlink_user", u);
    },
    [token, JSON.stringify(user)],
  );
}
const page = await context.newPage();
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
const offenders = await page.evaluate(() => {
  const width = document.documentElement.clientWidth;
  const out = [];
  for (const el of document.querySelectorAll("body *")) {
    const rect = el.getBoundingClientRect();
    if (rect.right > width + 1 && rect.width > 0) {
      // Report only the outermost offender of each branch.
      if (el.parentElement && el.parentElement.getBoundingClientRect().right > width + 1) continue;
      out.push(`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 90)} right=${Math.round(rect.right)} width=${Math.round(rect.width)}`);
    }
  }
  return { docWidth: document.documentElement.scrollWidth, out: out.slice(0, 15) };
});
console.log(JSON.stringify(offenders, null, 2));
await browser.close();
