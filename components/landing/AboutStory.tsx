"use client";

import Link from "next/link";
import { motion, type Variants } from "framer-motion";
import { ArrowLeft, ArrowRight, HeartPulse, ShieldCheck } from "lucide-react";

import { AmbientMedicalBackground } from "@/components/landing/PremiumLanding";

const paragraphs = [
  "Nora MedLink was created for patients who carry reports, prescriptions, symptoms, and worries, but still struggle to explain their health story clearly.",
  "Many patients forget important details during appointments. Some lose old reports. Some do not know which symptoms matter. At the same time, doctors often have limited time and incomplete patient history.",
  "Nora MedLink connects these missing pieces.",
  "It helps patients save their reports, medicine history, and health information in one place. It uses AI to organize this data, generate clear summaries, highlight possible risks, and support doctors in understanding the patient faster.",
  "Nora MedLink does not replace doctors. It supports better communication between patients and doctors, so healthcare feels more human, safer, and easier to understand.",
];

const fadeIn: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: "easeOut" },
  },
};

export function AboutStory() {
  return (
    <main className="premium-page text-slate-950">
      <AmbientMedicalBackground />

      <nav className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-5 py-6 sm:px-6 lg:px-8">
        <Link href="/" className="secondary-button gap-2 rounded-full px-4 py-2">
          <ArrowLeft className="h-4 w-4" />
          Home
        </Link>
        <Link href="/signup?role=patient" className="gradient-button rounded-full px-4 py-2">
          Get Started
        </Link>
      </nav>

      <motion.section
        className="relative z-10 mx-auto grid min-h-[calc(100vh-96px)] max-w-7xl items-center gap-10 px-5 py-16 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:px-8"
        initial="hidden"
        animate="show"
        variants={fadeIn}
      >
        <div>
          <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-cyan-50 text-cyan-700 ring-1 ring-cyan-100">
            <HeartPulse className="h-7 w-7" />
          </span>
          <p className="section-eyebrow mt-8">About Nora MedLink</p>
          <h1 className="mt-5 max-w-3xl text-4xl font-black leading-tight tracking-tight text-slate-950 [text-wrap:balance] sm:text-6xl">
            Better health stories create better conversations.
          </h1>
        </div>

        <div className="landing-glass rounded-[28px] p-6 sm:p-9">
          <div className="mb-7 flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-blue-50 text-blue-700 ring-1 ring-blue-100">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <div>
              <p className="text-sm font-black text-slate-950">Human-centered AI healthcare</p>
              <p className="text-xs font-semibold text-slate-500">Support, awareness, and clarity</p>
            </div>
          </div>

          <div className="space-y-5">
            {paragraphs.map((paragraph, index) => (
              <p
                key={paragraph}
                className={`leading-8 text-slate-600 ${
                  index === 2 ? "text-2xl font-black tracking-tight text-slate-950" : "text-base font-medium"
                }`}
              >
                {paragraph}
              </p>
            ))}
          </div>

          <Link href="/dashboard/patient" className="gradient-button mt-8 gap-2 px-5 py-3">
            Open Patient Dashboard
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </motion.section>
    </main>
  );
}
