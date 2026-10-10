import { Activity, BellRing, BrainCircuit, CalendarCheck, FileScan, KeyRound, type LucideIcon } from "lucide-react";

import { Reveal } from "./Reveal";

const FEATURES: Array<{ icon: LucideIcon; title: string; description: string }> = [
  {
    icon: FileScan,
    title: "Report upload with OCR",
    description: "Photograph or upload a lab report, prescription or scan. The text is read and filed under the right department.",
  },
  {
    icon: BrainCircuit,
    title: "Plain-language summaries",
    description: "Each report gets a short summary and highlighted values to discuss with your doctor. Advisory, never a diagnosis.",
  },
  {
    icon: Activity,
    title: "Vitals log",
    description: "Record blood pressure and sugar readings and see your recent history in one place.",
  },
  {
    icon: BellRing,
    title: "Medicine reminders",
    description: "Add your medicines, schedule reminders, and get a browser notification when a dose is due.",
  },
  {
    icon: KeyRound,
    title: "Doctor access by one-time code",
    description: "Generate a code for your doctor. It opens your vitals, reports and medicines for one consultation only.",
  },
  {
    icon: CalendarCheck,
    title: "Appointments with verified doctors",
    description: "Book with doctors whose registration an administrator has checked.",
  },
];

export function FeatureGrid() {
  return (
    <section id="features" className="scroll-mt-20 border-t border-line bg-white py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal className="max-w-2xl">
          <p className="section-eyebrow">Features</p>
          <h2 className="section-title mt-3">Everything about your health record, in one calm place.</h2>
        </Reveal>
        <ul className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, description }, index) => (
            <li key={title}>
              <Reveal delay={(index % 3) * 0.05} className="h-full">
                <article className="h-full rounded-card border border-line bg-surface-soft p-6 transition-colors hover:border-line-strong hover:bg-white">
                  <span className="grid h-11 w-11 place-items-center rounded-control bg-gradient-to-br from-brand-blue to-brand-teal text-white shadow-sm">
                    <Icon className="h-5 w-5" aria-hidden />
                  </span>
                  <h3 className="mt-5 text-base font-semibold text-ink">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-ink-muted">{description}</p>
                </article>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
