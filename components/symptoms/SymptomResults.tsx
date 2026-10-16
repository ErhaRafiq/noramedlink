import Link from "next/link";
import { Stethoscope } from "lucide-react";

import { DoctorCard } from "@/components/doctors/DoctorCard";
import { Alert } from "@/components/ui/alert";
import type { AppointmentDoctor, SymptomCheck } from "@/lib/types";

/** The kinds of doctor to see first, each with its reason and the verified doctors who can be booked. */
export function SymptomResults({
  result,
  canBook,
  onBook,
}: {
  result: SymptomCheck;
  canBook: boolean;
  onBook: (doctor: AppointmentDoctor) => void;
}) {
  return (
    <section aria-labelledby="results-title" className="space-y-5">
      <div>
        <h2 id="results-title" className="text-base font-semibold text-ink">
          {result.suggestions.length > 1 ? "Doctors you could see first" : "The doctor to see first"}
        </h2>
        <p className="mt-1 text-sm text-ink-muted">Based on the words you used. This is a suggestion, not a diagnosis.</p>
      </div>

      {result.suggestions.map((suggestion, index) => (
        <article key={suggestion.specialty} aria-label={suggestion.specialty} className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Stethoscope className="h-5 w-5 text-brand-blue" aria-hidden />
            <h3 className="text-base font-semibold text-ink">{suggestion.specialty}</h3>
            {index === 0 && result.suggestions.length > 1 ? <span className="text-xs font-medium text-brand-teal">Best match</span> : null}
          </div>
          <p className="mt-1 text-sm text-ink-muted">Looks after: {suggestion.plain}.</p>
          <p className="mt-2 text-sm text-ink">
            {suggestion.matched.length > 0
              ? `Suggested because you mentioned: ${suggestion.matched.join(", ")}.`
              : "No specific symptom word matched, so a general physician is a good first visit."}
          </p>

          {suggestion.doctors.length === 0 ? (
            <div className="mt-4 rounded-control border border-dashed border-line p-4 text-sm text-ink-muted">
              No verified {suggestion.specialty.toLowerCase()} is listed yet.{" "}
              <Link href="/doctors" className="font-semibold text-brand-blue underline">
                Browse all doctors
              </Link>
            </div>
          ) : (
            <ul className="mt-4 grid gap-4 sm:grid-cols-2">
              {suggestion.doctors.map((doctor) => (
                <li key={doctor.id} className="min-w-0">
                  <DoctorCard doctor={doctor} canBook={canBook} onBook={onBook} />
                </li>
              ))}
            </ul>
          )}
        </article>
      ))}

      <Alert tone="info" title="Advisory only">
        {result.advisory}
      </Alert>
    </section>
  );
}
