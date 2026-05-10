"use client";

import Link from "next/link";
import { motion, useReducedMotion, type Variants } from "framer-motion";
import {
  ArrowRight,
  Bell,
  BrainCircuit,
  CalendarCheck,
  FileText,
  HeartPulse,
  LockKeyhole,
  Search,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { FeatureCard } from "@/components/ui/saas-shell";

const features: Array<{
  title: string;
  description: string;
  href: string;
  icon: LucideIcon;
}> = [
  {
    title: "OCR Report Upload",
    description: "Upload clinical files and convert them into readable report text.",
    href: "/dashboard/patient/upload",
    icon: FileText,
  },
  {
    title: "AI Summaries",
    description: "Generate concise care summaries from saved reports and OCR text.",
    href: "/dashboard/patient/summary",
    icon: BrainCircuit,
  },
  {
    title: "Appointments",
    description: "Book doctor visits and keep upcoming consultations in view.",
    href: "/doctors",
    icon: CalendarCheck,
  },
  {
    title: "Medicine Reminders",
    description: "Track medicine history and reminder-ready treatment details.",
    href: "/dashboard/patient/profile",
    icon: Bell,
  },
  {
    title: "Secure Records",
    description: "Keep patient records organized behind authenticated access.",
    href: "/login",
    icon: LockKeyhole,
  },
];

const previewStats = [
  { label: "Uploaded Reports", value: "24" },
  { label: "AI Summaries", value: "18" },
  { label: "Appointments", value: "03" },
];

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.38, ease: "easeOut" },
  },
};

const stagger: Variants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.07,
      delayChildren: 0.04,
    },
  },
};

export function PremiumLanding() {
  const reduceMotion = useReducedMotion();
  const initialState = reduceMotion ? "show" : "hidden";

  return (
    <main className="premium-page text-slate-950">
      <AmbientMedicalBackground />
      <Navigation />

      <motion.section
        className="relative z-10 px-5 pb-16 pt-28 sm:px-6 lg:px-8"
        initial={initialState}
        animate="show"
        variants={stagger}
      >
        <div className="mx-auto grid min-h-[calc(100vh-7rem)] max-w-7xl items-center gap-10 lg:grid-cols-[1.02fr_0.98fr]">
          <div className="max-w-4xl">
            <motion.p variants={fadeUp} className="section-eyebrow">
              AI-powered healthcare workflows
            </motion.p>
            <motion.h1
              variants={fadeUp}
              className="mt-5 max-w-5xl text-4xl font-black leading-tight tracking-tight text-[#0B1220] [text-wrap:balance] sm:text-6xl lg:text-7xl"
            >
              Smarter records. Better care. All in one place.
            </motion.h1>
            <motion.p
              variants={fadeUp}
              className="mt-6 max-w-2xl text-base leading-8 text-slate-600 sm:text-lg"
            >
              Nora MedLink brings OCR reports, AI summaries, appointments, medicine reminders, and secure patient records into one clean healthcare workspace.
            </motion.p>
            <motion.div variants={fadeUp} className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link href="/signup?role=patient" className="gradient-button group gap-2 px-6 py-3.5">
                Get Started
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              </Link>
              <Link href="#features" className="secondary-button gap-2 px-6 py-3.5">
                See how it works
                <Search className="h-4 w-4" />
              </Link>
            </motion.div>
          </div>

          <motion.div variants={fadeUp} className="relative mx-auto w-full max-w-xl">
            <div className="landing-glass rounded-[28px] p-5">
              <div className="rounded-[22px] border border-[#DCE8F5] bg-white p-5 shadow-inner shadow-blue-900/5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
                      Verification ready
                    </p>
                    <h2 className="mt-2 text-2xl font-black tracking-tight text-[#0B1220]">
                      Patient dashboard
                    </h2>
                  </div>
                  <span className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-[#2563EB] to-[#00BFA6] text-white shadow-lg shadow-teal-500/20">
                    <HeartPulse className="h-7 w-7" />
                  </span>
                </div>

                <div className="mt-6 grid gap-3 sm:grid-cols-3">
                  {previewStats.map((card) => (
                    <div key={card.label} className="rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-4">
                      <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">{card.label}</p>
                      <p className="mt-3 text-2xl font-black text-[#0B1220]">{card.value}</p>
                    </div>
                  ))}
                </div>

                <div className="mt-5 rounded-2xl border border-teal-100 bg-teal-50/80 p-4">
                  <div className="flex items-center gap-3">
                    <Sparkles className="h-5 w-5 text-teal-600" />
                    <p className="text-sm font-bold leading-6 text-teal-950">
                      Latest OCR report summarized for doctor review.
                    </p>
                  </div>
                </div>

                <div className="mt-5 space-y-3">
                  {["CBC Lab Report", "Cardiology Summary", "Medicine History"].map((item, index) => (
                    <div key={item} className="flex items-center justify-between rounded-2xl border border-[#DCE8F5] bg-white px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-700">
                          {index === 0 ? <FileText className="h-4 w-4" /> : index === 1 ? <BrainCircuit className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
                        </span>
                        <p className="text-sm font-black text-[#0B1220]">{item}</p>
                      </div>
                      <span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-black text-teal-700">
                        Ready
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </motion.section>

      <motion.section
        id="features"
        className="relative z-10 px-5 pb-20 sm:px-6 lg:px-8"
        initial={initialState}
        whileInView="show"
        viewport={{ once: true, amount: 0.25 }}
        variants={stagger}
      >
        <div className="mx-auto max-w-7xl">
          <motion.div variants={fadeUp} className="max-w-2xl">
            <p className="section-eyebrow">Features</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-[#0B1220] sm:text-4xl">
              Core healthcare workflows.
            </h2>
          </motion.div>

          <div className="mt-9 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {features.map((feature) => (
              <motion.div key={feature.title} variants={fadeUp}>
                <FeatureCard {...feature} />
              </motion.div>
            ))}
          </div>
        </div>
      </motion.section>

      <section id="contact" className="relative z-10 px-5 pb-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-[28px] bg-gradient-to-br from-[#2563EB] to-[#00BFA6] p-8 text-white shadow-[0_24px_70px_rgba(37,99,235,0.18)] sm:p-10">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-50">
                Secure care workspace
              </p>
              <h2 className="mt-3 text-3xl font-black tracking-tight">
                Start organizing patient records with Nora MedLink.
              </h2>
            </div>
            <Link href="/signup?role=patient" className="inline-flex w-fit items-center justify-center rounded-[14px] bg-white px-6 py-3 text-sm font-black text-[#082A46] shadow-lg shadow-blue-950/10">
              Create account
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}

function Navigation() {
  return (
    <motion.nav
      className="fixed left-0 right-0 top-0 z-40 px-5 py-5 sm:px-6 lg:px-8"
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: "easeOut" }}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 rounded-full border border-[#DCE8F5] bg-white/90 px-4 py-3 shadow-[0_16px_40px_rgba(15,23,42,0.06)] backdrop-blur-2xl">
        <Link href="/" className="flex items-center gap-3" aria-label="Nora MedLink home">
          <span className="relative grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-[#2563EB] to-[#00BFA6] text-white shadow-lg shadow-teal-500/20">
            <HeartPulse className="h-5 w-5" />
          </span>
          <span>
            <span className="block text-sm font-black tracking-tight text-[#0B1220] sm:text-base">
              Nora MedLink
            </span>
            <span className="hidden text-[10px] font-bold uppercase tracking-[0.18em] text-teal-700 sm:block">
              Healthcare SaaS
            </span>
          </span>
        </Link>

        <div className="hidden items-center gap-7 text-sm font-bold text-slate-600 md:flex">
          <Link href="/" className="transition hover:text-blue-700">
            Home
          </Link>
          <Link href="#features" className="transition hover:text-blue-700">
            Features
          </Link>
          <Link href="/about" className="transition hover:text-blue-700">
            About
          </Link>
          <Link href="#contact" className="transition hover:text-blue-700">
            Contact
          </Link>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/login" className="secondary-button hidden rounded-full px-4 py-2 sm:inline-flex">
            Login
          </Link>
          <Link href="/signup?role=patient" className="gradient-button rounded-full px-4 py-2">
            Signup
          </Link>
        </div>
      </div>
    </motion.nav>
  );
}

export function AmbientMedicalBackground() {
  return (
    <div aria-hidden="true" className="absolute inset-0 overflow-hidden">
      <div className="ambient-glow" />
      <div className="ambient-grid" />
      <div className="absolute left-0 right-0 top-24 h-px bg-gradient-to-r from-transparent via-blue-200 to-transparent" />
      <div className="absolute bottom-36 left-0 right-0 h-px bg-gradient-to-r from-transparent via-teal-200 to-transparent" />
    </div>
  );
}
