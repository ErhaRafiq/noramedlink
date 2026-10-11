import { runFixtures } from "./support/fixtures-file";

/** Removes the phase0-test- users, their rows and upload folders, even after failures. */
export default function globalTeardown() {
  runFixtures(["cleanup"]);
}
