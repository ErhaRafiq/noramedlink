// Report departments live in lib/departments.ts (mirroring the backend).

/**
 * Human label for a report's validation status. SAFE only means no rule raised an alert,
 * so it is never shown as "safe" (AGENTS.md 6.2).
 */
export function validationLabel(status: string | null | undefined) {
  const value = (status ?? "").toUpperCase();
  if (value === "HIGH_RISK") return "High risk";
  if (value === "CAUTION") return "Caution";
  if (value === "SAFE") return "No rule alerts";
  return "Not validated";
}

/** The note every AI output carries (AGENTS.md section 6, rule 4). */
export function buildMedicalDisclaimer() {
  return "AI-generated and advisory only. This is not a diagnosis; verify with a clinician.";
}
