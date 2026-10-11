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
  runFixtures(["setup", FIXTURES_FILE]);
}
