import { ArrowRight, BadgeCheck, KeyRound, ShieldCheck } from "lucide-react";

import { ButtonLink } from "@/components/ui/button";
import { HeroVisual } from "./HeroVisual";
import { Reveal } from "./Reveal";

const TRUST_POINTS = [
  { icon: KeyRound, label: "Doctors see your file only with your one-time code" },
  { icon: BadgeCheck, label: "Only admin-verified doctors can be booked" },
  { icon: ShieldCheck, label: "AI summaries are advisory, never a diagnosis" },
];

export function Hero() {
  return (
    <section className="relative mx-auto grid max-w-6xl items-center gap-10 px-4 pb-16 pt-10 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:pb-24 lg:pt-16">
      <Reveal>
        <p className="section-eyebrow">Patient records, made understandable</p>
        <h1 className="mt-4 text-4xl font-semibold leading-[1.1] tracking-tight text-ink sm:text-5xl lg:text-6xl">
          Your medical reports, organised and explained.
        </h1>
        <p className="mt-5 max-w-xl text-base leading-7 text-ink-muted sm:text-lg">
          Upload lab reports and prescriptions, read a plain-language summary, keep track of vitals and medicines, and share
          your record with your doctor when you choose.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <ButtonLink href="/signup?role=patient" size="lg" icon={<ArrowRight className="h-4 w-4" />} className="flex-row-reverse">
            Create your account
          </ButtonLink>
          <ButtonLink href="/login" variant="secondary" size="lg">
            Sign in
          </ButtonLink>
        </div>
        <ul className="mt-10 space-y-3">
          {TRUST_POINTS.map(({ icon: Icon, label }) => (
            <li key={label} className="flex items-center gap-3 text-sm text-slate-600">
              <span className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-full bg-teal-50 text-teal-700">
                <Icon className="h-4 w-4" aria-hidden />
              </span>
              {label}
            </li>
          ))}
        </ul>
      </Reveal>

      <Reveal delay={0.1} className="flex justify-center lg:justify-end">
        <HeroVisual />
      </Reveal>
    </section>
  );
}
