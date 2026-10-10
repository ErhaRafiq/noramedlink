import { Phone, ShieldAlert } from "lucide-react";

import { Reveal } from "./Reveal";

/** The project's safety position (AGENTS.md section 6), stated plainly on the public page. */
export function SafetyNote() {
  return (
    <section id="safety" className="scroll-mt-20 pb-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal>
          <div className="grid gap-6 rounded-card border border-amber-200 bg-amber-50/70 p-6 sm:p-8 md:grid-cols-[auto_1fr]">
            <span className="grid h-11 w-11 place-items-center rounded-control bg-amber-100 text-amber-700">
              <ShieldAlert className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <h2 className="text-lg font-semibold text-ink">An academic prototype, advisory only</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-700">
                Nora MedLink is a final-year project, not a certified medical device. It does not diagnose or prescribe.
                Summaries and flags are generated automatically and must be checked by a qualified clinician.
              </p>
              <p className="mt-4 inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-rose-700 shadow-sm">
                <Phone className="h-4 w-4" aria-hidden />
                In an emergency, call 1122 or go to the nearest emergency department.
              </p>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
