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

const AI_NAMES: Record<string, string> = { gemini: "Gemini", openai: "OpenAI", groq: "Groq" };

/**
 * Label and note for a summary, by who wrote it: an AI model (with the AI note, AGENTS.md 6.4)
 * or the app's fixed rules. Unknown or missing sources count as rule-based.
 */
export function summaryOrigin(source: string | null | undefined) {
  const ai = source ? AI_NAMES[source] : undefined;
  return ai
    ? { aiWritten: true, label: `AI-generated summary (${ai})`, note: buildMedicalDisclaimer() }
    : {
        aiWritten: false,
        label: "Summary built by fixed rules",
        note: "Built by fixed rules from the report text, not by AI. Advisory only; this is not a diagnosis. Verify with a clinician.",
      };
}

/** The note every AI output carries (AGENTS.md section 6, rule 4). */
export function buildMedicalDisclaimer() {
  return "AI-generated and advisory only. This is not a diagnosis; verify with a clinician.";
}
