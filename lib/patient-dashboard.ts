// Report departments live in lib/departments.ts (mirroring the backend).

/** Human label for a report's validation status ("HIGH_RISK" -> "HIGH RISK"). */
export function validationLabel(status: string | null | undefined) {
  const value = (status ?? "").toUpperCase();
  if (value === "NOT_VALIDATED" || !value) return "Not validated";
  return value.replaceAll("_", " ");
}

/** The note every AI output carries (AGENTS.md section 6, rule 4). */
export function buildMedicalDisclaimer() {
  return "AI-generated and advisory only. This is not a diagnosis; verify with a clinician.";
}
