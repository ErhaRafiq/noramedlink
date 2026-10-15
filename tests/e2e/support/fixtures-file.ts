import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";

export const BASE_URL = (process.env.E2E_BASE_URL ?? "http://localhost:3000").replace(/\/$/, "");

const ROOT = path.resolve(__dirname, "..", "..", "..");
const PYTHON = path.join(ROOT, "backend", "venv", "Scripts", "python.exe");
const SCRIPT = path.join(ROOT, "tests", "e2e", "fixtures.py");

/** Written by fixtures.py; test-results/ is git-ignored. */
export const FIXTURES_FILE = path.join(ROOT, "test-results", "e2e-users.json");

export type Role = "patient" | "doctor" | "admin";

export type TestUser = { id: number; email: string; fullName: string; role: Role; token: string };

export type Fixtures = {
  run: string;
  password: string;
  reportId: number;
  attentionReportId: number;
  ocrKeySet: boolean;
  /** Stripe Checkout is on: paying would open Stripe's page, so payment tests skip. */
  stripeKeySet: boolean;
  aiKeySet: boolean;
  users: Record<"patient" | "patientEmpty" | "doctor" | "doctorWithAccess" | "doctorPendingA" | "doctorPendingB" | "doctorUnreviewed" | "admin", TestUser>;
};

export function runFixtures(args: string[]) {
  execFileSync(PYTHON, [SCRIPT, ...args], {
    cwd: ROOT,
    stdio: "inherit",
    env: { ...process.env, HF_HUB_OFFLINE: "1" },
  });
}

let cached: Fixtures | null = null;

export function fixtures(): Fixtures {
  cached ??= JSON.parse(readFileSync(FIXTURES_FILE, "utf8")) as Fixtures;
  return cached;
}
