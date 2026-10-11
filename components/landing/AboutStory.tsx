import { ArrowRight, GraduationCap, HeartHandshake, ShieldCheck } from "lucide-react";

import { PageContainer } from "@/components/layout/PageHeader";
import { ButtonLink } from "@/components/ui/button";
import { Reveal } from "./Reveal";

const STORY = [
  "Many patients carry a folder of reports, prescriptions and notes, yet still find it hard to explain their health history in a short appointment. Reports get lost, details are forgotten, and doctors see an incomplete picture.",
  "Nora MedLink keeps that history in one place. It reads uploaded reports, files them by department, writes a plain-language summary, and lets the patient share everything with a doctor for one consultation using a one-time code.",
  "It does not replace doctors. Summaries and flags are advisory: they help patients ask better questions and help doctors get up to speed faster.",
];

const PRINCIPLES = [
  { icon: HeartHandshake, title: "The patient decides", text: "A doctor sees a file only with a one-time code the patient gives them, and only for that consultation." },
  { icon: ShieldCheck, title: "Advisory, never a diagnosis", text: "Every automated summary carries a note to verify it with a clinician. In an emergency, call 1122." },
  { icon: GraduationCap, title: "An academic prototype", text: "A final-year project in BS Data Science at COMSATS University Islamabad, by Erha Rafiq and Momna Javed." },
];

export function AboutStory() {
  return (
    <PageContainer narrow className="py-12 lg:py-16">
      <Reveal>
        <p className="section-eyebrow">About Nora MedLink</p>
        <h1 className="mt-3 text-4xl font-semibold leading-tight tracking-tight text-ink sm:text-5xl">
          Better health stories make better conversations.
        </h1>
      </Reveal>

      <div className="mt-8 space-y-5">
        {STORY.map((paragraph) => (
          <p key={paragraph} className="text-base leading-8 text-slate-600 sm:text-lg">
            {paragraph}
          </p>
        ))}
      </div>

      <ul className="mt-12 grid gap-4 sm:grid-cols-3">
        {PRINCIPLES.map(({ icon: Icon, title, text }, index) => (
          <li key={title}>
            <Reveal delay={index * 0.05} className="h-full">
              <div className="h-full rounded-card border border-line bg-white p-5 shadow-card">
                <Icon className="h-5 w-5 text-brand-blue" aria-hidden />
                <h2 className="mt-3 text-sm font-semibold text-ink">{title}</h2>
                <p className="mt-1.5 text-sm leading-6 text-ink-muted">{text}</p>
              </div>
            </Reveal>
          </li>
        ))}
      </ul>

      <div className="mt-12 flex flex-col gap-3 sm:flex-row">
        <ButtonLink href="/signup?role=patient" size="lg" icon={<ArrowRight className="h-4 w-4" />} className="flex-row-reverse">
          Create your account
        </ButtonLink>
        <ButtonLink href="/doctors" variant="secondary" size="lg">
          Find a doctor
        </ButtonLink>
      </div>
    </PageContainer>
  );
}
