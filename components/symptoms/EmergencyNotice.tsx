import { PhoneCall } from "lucide-react";

import type { SymptomCheck } from "@/lib/types";

/** What a warning sign shows instead of any specialist or booking (AGENTS.md section 6, rule 3). */
export function EmergencyNotice({ result, onRestart }: { result: SymptomCheck; onRestart: () => void }) {
  const selfHarm = result.warning_signs.some((sign) => sign.toLowerCase().includes("harming"));
  return (
    <section role="alert" aria-labelledby="emergency-title" className="rounded-card border border-rose-200 bg-rose-50 p-5 shadow-card sm:p-6">
      <div className="flex items-start gap-3">
        <PhoneCall className="mt-1 h-6 w-6 flex-shrink-0 text-rose-600" aria-hidden />
        <div className="min-w-0">
          <h2 id="emergency-title" className="text-lg font-semibold text-rose-900">
            This may be an emergency
          </h2>
          <p className="mt-1 break-words text-base font-semibold text-rose-900">{result.emergency_notice}</p>
          <p className="mt-2 text-sm leading-6 text-rose-900">Do not wait for an appointment. If you can, ask someone to stay with you.</p>
          {selfHarm ? (
            <p className="mt-2 text-sm leading-6 text-rose-900">
              If you are thinking about harming yourself, tell someone you trust right now and do not stay alone.
            </p>
          ) : null}
        </div>
      </div>
      <div className="mt-4 border-t border-rose-200 pt-4">
        <p className="text-sm font-medium text-rose-900">What we noticed in your description</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-rose-900">
          {result.warning_signs.map((sign) => (
            <li key={sign}>{sign}</li>
          ))}
        </ul>
      </div>
      <button type="button" onClick={onRestart} className="mt-4 text-sm font-semibold text-rose-900 underline">
        Start again
      </button>
    </section>
  );
}
