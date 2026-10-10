import { ArrowRight, Stethoscope } from "lucide-react";

import { ButtonLink } from "@/components/ui/button";
import { Reveal } from "./Reveal";

export function CallToAction() {
  return (
    <section className="pb-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal>
          <div className="flex flex-col gap-6 rounded-card bg-gradient-to-br from-brand-blue to-brand-teal p-8 text-white shadow-calm sm:p-10 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Start with your next report.</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-blue-50">
                Patients sign up in a minute. Doctors can join too; an administrator verifies each registration first.
              </p>
            </div>
            <div className="flex flex-shrink-0 flex-col gap-3 sm:flex-row">
              <ButtonLink
                href="/signup?role=patient"
                variant="secondary"
                size="lg"
                className="flex-row-reverse border-white text-brand-navy"
                icon={<ArrowRight className="h-4 w-4" />}
              >
                Create a patient account
              </ButtonLink>
              <ButtonLink
                href="/signup?role=doctor"
                variant="ghost"
                size="lg"
                className="border border-white/40 text-white hover:bg-white/10 hover:text-white"
                icon={<Stethoscope className="h-4 w-4" />}
              >
                Join as a doctor
              </ButtonLink>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
