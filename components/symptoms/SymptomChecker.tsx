"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Search } from "lucide-react";

import { BookingDialog } from "@/components/doctors/BookingDialog";
import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextAreaField } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyAppointments } from "@/hooks/doctors/use-my-appointments";
import { usePrefersReducedMotion } from "@/hooks/use-media-query";
import { useSymptomCheck } from "@/hooks/symptoms/use-symptom-check";
import { useStoredSession } from "@/hooks/use-stored-session";
import type { AppointmentDoctor } from "@/lib/types";
import { EmergencyNotice } from "./EmergencyNotice";
import { SymptomResults } from "./SymptomResults";

const MAX_LENGTH = 1000;
const EXAMPLES = ["Itchy rash on my arm for a week", "Fever and sore throat for 2 days", "Knee pain when I climb stairs"];

type Notice = { tone: "success" | "warning"; text: string } | null;

export function SymptomChecker() {
  const { session } = useStoredSession();
  const isPatient = session?.user.role === "patient";
  const { result, checking, error, check, reset } = useSymptomCheck();
  const appointments = useMyAppointments(isPatient);
  const [text, setText] = useState("");
  const [booking, setBooking] = useState<AppointmentDoctor | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const outcomeRef = useRef<HTMLDivElement>(null);
  const reduceMotion = usePrefersReducedMotion();

  // On a phone the answer lands below the form: bring it into view (and, for an emergency, first).
  const hasOutcome = result !== null || error !== "";
  useEffect(() => {
    if (hasOutcome) outcomeRef.current?.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" });
  }, [hasOutcome, result, reduceMotion]);

  const tooShort = text.trim().length < 3;
  const busyTimes = useMemo(
    () =>
      appointments.appointments
        .filter((a) => a.status === "BOOKED")
        .map((a) => ({ start: a.date, end: new Date(new Date(a.date).getTime() + a.duration_minutes * 60_000).toISOString() })),
    [appointments.appointments],
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    if (tooShort || checking) return;
    setNotice(null);
    void check(text.trim());
  }

  function startAgain() {
    reset();
    setText("");
    setNotice(null);
  }

  function startBooking(doctor: AppointmentDoctor) {
    setNotice(null);
    if (!session) {
      setNotice({ tone: "warning", text: "Please sign in as a patient to book an appointment." });
      return;
    }
    if (!isPatient) {
      setNotice({ tone: "warning", text: "Only patient accounts can book appointments." });
      return;
    }
    setBooking(doctor);
  }

  async function booked(message: string) {
    setBooking(null);
    setNotice({ tone: "success", text: message });
    await appointments.reload();
  }

  return (
    <PageContainer narrow>
      <PageHeader
        eyebrow="Symptoms"
        title="Which doctor should I see?"
        description="Describe how you feel in your own words. We suggest the kind of doctor to see first. This is not a diagnosis."
      />

      <Alert tone="warning" className="mb-6" title="In an emergency, do not use this page">
        Call 1122 or go to the nearest emergency department.
      </Alert>

      <form onSubmit={submit} className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6" aria-label="Symptom checker">
        <TextAreaField
          label="Your symptoms"
          placeholder="For example: itchy rash on my arm for a week"
          value={text}
          maxLength={MAX_LENGTH}
          rows={4}
          onChange={(event) => setText(event.target.value)}
          hint={`${text.length} of ${MAX_LENGTH} characters. English only. Do not include your name or phone number.`}
        />
        <div className="mt-3 flex flex-wrap gap-2" aria-label="Examples">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setText(example)}
              className="rounded-full border border-line bg-surface-soft px-3 py-1.5 text-xs text-slate-700 transition-colors hover:border-brand-blue hover:text-brand-blue focus-visible:ring-2 focus-visible:ring-brand-blue"
            >
              {example}
            </button>
          ))}
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button type="submit" loading={checking} disabled={tooShort} icon={<Search className="h-4 w-4" />}>
            {checking ? "Checking..." : "Check my symptoms"}
          </Button>
          {result ? (
            <Button type="button" variant="ghost" onClick={startAgain} disabled={checking}>
              Start again
            </Button>
          ) : null}
        </div>
      </form>

      <div ref={outcomeRef} className="mt-6 scroll-mt-20 space-y-4" aria-live="polite">
        {notice ? (
          <Alert tone={notice.tone} title={notice.tone === "success" ? "Booked" : undefined}>
            {notice.text}{" "}
            {notice.tone === "success" ? (
              <Link href="/doctors" className="font-semibold underline">
                See my appointments
              </Link>
            ) : !session ? (
              <Link href="/login" className="font-semibold underline">
                Sign in
              </Link>
            ) : null}
          </Alert>
        ) : null}

        {checking ? (
          <div role="status" aria-label="Checking your symptoms" className="space-y-3 rounded-card border border-line bg-white p-5 shadow-card">
            <Skeleton className="h-5 w-1/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : error ? (
          <Alert tone="error" title="The check could not be completed">
            {error}
          </Alert>
        ) : result?.emergency ? (
          <EmergencyNotice result={result} onRestart={startAgain} />
        ) : result ? (
          <SymptomResults result={result} canBook={session === null || isPatient} onBook={startBooking} />
        ) : null}
      </div>

      <BookingDialog doctor={booking} busy={busyTimes} onClose={() => setBooking(null)} onBooked={(message) => void booked(message)} />
    </PageContainer>
  );
}
