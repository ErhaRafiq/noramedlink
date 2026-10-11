import { defineConfig, devices } from "@playwright/test";

/**
 * Integration tests (tests/e2e) against the running app, in the installed Microsoft Edge.
 *
 * Start FastAPI (port 8000) and `npm run dev` first, then: `npm run test:e2e`.
 * Test users are created and removed by tests/e2e/fixtures.py (phase0-test- only, localhost
 * databases only). Do not run this and tests/acceptance_test.py at the same time.
 */
const baseURL = (process.env.E2E_BASE_URL ?? "http://localhost:3000").replace(/\/$/, "");

export default defineConfig({
  testDir: "tests/e2e",
  outputDir: "test-results/e2e",
  globalSetup: "./tests/e2e/global-setup.ts",
  globalTeardown: "./tests/e2e/global-teardown.ts",
  // One worker: the tests share one database and the API's rate limits.
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { outputFolder: "test-results/e2e-report", open: "never" }]],
  use: {
    baseURL,
    channel: "msedge",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 45_000,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Edge"], channel: "msedge" }, grepInvert: /@mobile/ },
    {
      name: "mobile",
      use: { channel: "msedge", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
      grep: /@mobile/,
    },
  ],
});
