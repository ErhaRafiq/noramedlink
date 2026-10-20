import { BASE_URL, FIXTURES_FILE, runFixtures } from "./support/fixtures-file";

/** Checks both servers are up, then creates the phase0-test- users. */
export default async function globalSetup() {
  const checks: Array<[string, string]> = [
    ["Next.js (npm run dev)", BASE_URL],
    ["FastAPI (uvicorn main:app --port 8000)", `${BASE_URL}/api/backend/health`],
  ];
  for (const [name, url] of checks) {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
    } catch (error) {
      throw new Error(`${name} is not reachable at ${url} (${(error as Error).message}). Start it first.`);
    }
  }
  // The first report that needs the language models waits for them to load (a minute or two): wait here instead,
  // so no test times out on a cold backend. /health says "ready" once the backend has loaded them.
  const deadline = Date.now() + 5 * 60_000;
  while (Date.now() < deadline) {
    const health = (await (await fetch(`${BASE_URL}/api/backend/health`)).json()) as { models?: string };
    if (health.models !== "loading") break;
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  runFixtures(["setup", FIXTURES_FILE]);
}
