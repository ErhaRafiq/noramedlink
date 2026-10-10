import { Reveal } from "./Reveal";

const STEPS = [
  {
    title: "Upload a report",
    description: "Add a photo or PDF of a lab result or prescription from your phone or computer.",
  },
  {
    title: "Read the summary",
    description: "Check the extracted text, correct it if needed, and read the advisory summary.",
  },
  {
    title: "Share with your doctor",
    description: "Generate a one-time code during your visit. Access ends when the consultation does.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal className="max-w-2xl">
          <p className="section-eyebrow">How it works</p>
          <h2 className="section-title mt-3">Three steps from paper report to an informed conversation.</h2>
        </Reveal>
        <ol className="mt-12 grid gap-6 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title}>
              <Reveal delay={index * 0.06} className="h-full">
                <div className="h-full rounded-card border border-line bg-white p-6 shadow-card">
                  <span className="grid h-9 w-9 place-items-center rounded-full bg-blue-50 text-sm font-semibold text-brand-blue">
                    {index + 1}
                  </span>
                  <h3 className="mt-5 text-base font-semibold text-ink">{step.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-ink-muted">{step.description}</p>
                </div>
              </Reveal>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
