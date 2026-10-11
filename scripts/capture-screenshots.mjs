/**
 * Captures screenshots of pages for visual review, using the installed Microsoft Edge.
 *
 *   node scripts/capture-screenshots.mjs <outDir> <baseUrl> [tokens.json] [only]
 *
 * tokens.json (optional): {"patient": "<jwt>", "doctor": "<jwt>", "admin": "<jwt>"} for
 * signed-in pages; the script asks /api/auth/me for each user and stores the session in
 * localStorage the same way the app does after sign in. `only` filters pages by name.
 */
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const [outDir = "screenshots", baseUrl = "http://localhost:3000", tokensFile, only] = process.argv.slice(2);

const PAGES = [
  { name: "landing", path: "/" },
  { name: "about", path: "/about" },
  { name: "login", path: "/login" },
  { name: "signup", path: "/signup?role=patient" },
  { name: "signup-doctor", path: "/signup?role=doctor" },
  { name: "doctors", path: "/doctors" },
  { name: "emergency", path: "/emergency" },
  { name: "payments", path: "/payments" },
  { name: "summarize", path: "/summarize" },
  { name: "not-found", path: "/this-page-does-not-exist" },
  { name: "doctors", path: "/doctors", as: "patient" },
  { name: "emergency", path: "/emergency", as: "patient" },
  { name: "payments", path: "/payments", as: "patient" },
  { name: "summarize", path: "/summarize", as: "patient" },
  { name: "patient-dashboard", path: "/dashboard/patient", as: "patient" },
  { name: "doctor-dashboard", path: "/dashboard/doctor", as: "doctor" },
  { name: "admin", path: "/admin", as: "admin" },
  // Set REPORT_ID to a report owned by the test patient to capture its detail page.
  ...(process.env.REPORT_ID ? [{ name: "report-detail", path: `/dashboard/patient/reports/${process.env.REPORT_ID}`, as: "patient" }] : []),
];

const VIEWPORTS = [
  { name: "desktop", viewport: { width: 1440, height: 900 }, isMobile: false },
  { name: "mobile", viewport: { width: 390, height: 844 }, isMobile: true },
];

async function sessionFor(role, tokens) {
  const token = tokens[role];
  const response = await fetch(`${baseUrl}/api/backend/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error(`/api/auth/me for ${role} returned ${response.status}`);
  return { token, user: await response.json() };
}

const tokens = tokensFile ? JSON.parse(readFileSync(tokensFile, "utf8")) : {};
const sessions = {};
for (const role of Object.keys(tokens)) sessions[role] = await sessionFor(role, tokens);

mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  for (const page of PAGES) {
    if (page.as && !sessions[page.as]) continue;
    const label = page.as ? `${page.name}-${page.as}` : page.name;
    if (only && !label.includes(only)) continue;
    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({ viewport: vp.viewport, isMobile: vp.isMobile, deviceScaleFactor: 1, reducedMotion: "reduce" });
      if (page.as) {
        const { token, user } = sessions[page.as];
        await context.addInitScript(
          ([t, u]) => {
            localStorage.setItem("nora_medlink_token", t);
            localStorage.setItem("nora_medlink_user", u);
          },
          [token, JSON.stringify(user)],
        );
      }
      const tab = await context.newPage();
      const errors = [];
      tab.on("pageerror", (error) => errors.push(error.message));
      tab.on("console", (message) => message.type() === "error" && errors.push(message.text()));
      await tab.goto(`${baseUrl}${page.path}`, { waitUntil: "networkidle" });
      await tab.waitForTimeout(800);
      const file = path.join(outDir, `${label}-${vp.name}.png`);
      await tab.screenshot({ path: file, fullPage: true });
      console.log(`${file}${errors.length ? `  ERRORS: ${errors.join(" | ").slice(0, 300)}` : ""}`);
      await context.close();
    }
  }
} finally {
  await browser.close();
}
