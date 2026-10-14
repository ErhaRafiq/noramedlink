import { AlertOctagon, AlertTriangle, HeartPulse } from "lucide-react";

import { cn } from "@/lib/cn";
import type { MedicalDocument, RuleWarning } from "@/lib/types";

/** What the patient should notice first: urgent alerts in red, points to discuss in amber, and the
 * conditions the report mentions. Everything comes from the app's fixed rules and the report text;
 * the alerts are in everyday words (the clinical wording is kept for the doctor). */
export function ReportAttention({ report, compact = false }: { report: MedicalDocument; compact?: boolean }) {
  const warnings = report.rule_warnings ?? report.structured_data_json?.rule_warnings ?? [];
  const urgent = warnings.filter((w) => w.severity === "HIGH_RISK");
  const caution = warnings.filter((w) => w.severity === "CAUTION");
  const conditions = report.conditions_mentioned ?? [];
  if (!urgent.length && !caution.length && !conditions.length) return null;

  return (
    <div className={cn("space-y-3", compact ? "mt-3" : "mt-6")}>
      {urgent.length > 0 && (
        <section role="alert" aria-label="Needs prompt attention" className="rounded-card border-2 border-rose-300 bg-rose-50 p-4 text-rose-900">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <AlertOctagon className="h-5 w-5 flex-shrink-0 text-rose-600" aria-hidden />
            Needs prompt attention from a doctor
          </h2>
          <WarningList warnings={urgent} compact={compact} />
          <p className="mt-2 text-xs font-medium">
            Please contact your doctor soon. If you feel very unwell, call 1122 or go to the nearest emergency department.
          </p>
        </section>
      )}

      {caution.length > 0 && (
        <section aria-label="Points to go over with your doctor" className="rounded-card border border-amber-200 bg-amber-50 p-4 text-amber-900">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <AlertTriangle className="h-5 w-5 flex-shrink-0 text-amber-600" aria-hidden />
            Points to go over with your doctor
          </h2>
          <WarningList warnings={caution} compact={compact} />
        </section>
      )}

      {conditions.length > 0 && (
        <section aria-label="Conditions mentioned in your report" className="rounded-card border border-blue-200 bg-blue-50 p-4 text-blue-950">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <HeartPulse className="h-5 w-5 flex-shrink-0 text-brand-blue" aria-hidden />
            Conditions mentioned in your report
          </h2>
          <ul className="mt-2 flex flex-wrap gap-2">
            {conditions.map((condition) => (
              <li
                key={condition.name}
                className={cn(
                  "min-w-0 break-words rounded-full border px-3 py-1 text-xs font-semibold",
                  condition.chronic ? "border-amber-300 bg-white text-amber-900" : "border-blue-200 bg-white text-blue-900",
                )}
              >
                {capitalise(condition.plain)}
                {condition.plain.toLowerCase() !== condition.name.toLowerCase() && <span className="font-normal opacity-75"> ({condition.name})</span>}
                {condition.chronic && <span className="ml-1 font-normal">· long-term</span>}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs">Mentioned in your report. The app does not diagnose; ask your doctor what these mean for you.</p>
        </section>
      )}
    </div>
  );
}

function WarningList({ warnings, compact }: { warnings: RuleWarning[]; compact: boolean }) {
  const shown = compact ? warnings.slice(0, 3) : warnings;
  return (
    <ul className="mt-2 space-y-1.5 text-sm leading-6">
      {shown.map((warning, index) => (
        <li key={`${warning.code}-${index}`} className="break-words">
          {warning.patient_message ?? warning.message}
        </li>
      ))}
      {compact && warnings.length > shown.length && <li className="text-xs opacity-80">and {warnings.length - shown.length} more on the report page</li>}
    </ul>
  );
}

function capitalise(text: string) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
