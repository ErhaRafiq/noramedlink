"use client";

import { useState } from "react";
import { CalendarDays, Stethoscope } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { clinicDateTime } from "@/lib/datetime";
import type { Appointment } from "@/lib/types";
import { DashCard } from "./ui";

const APPOINTMENTS_PREVIEW = 4;
const TONE: Record<string, BadgeTone> = { BOOKED: "success", COMPLETED: "info", CANCELLED: "danger", NO_SHOW: "danger" };
const LABEL: Record<string, string> = { BOOKED: "Booked", COMPLETED: "Completed", CANCELLED: "Cancelled", NO_SHOW: "Missed" };

/** The patient's next appointments. Booking, moving, cancelling and rating happen on the Find a doctor page. */
export function AppointmentsSection({ appointments }: { appointments: Appointment[] }) {
  const [now] = useState(() => Date.now());
  const upcoming = appointments
    .filter((a) => a.status.toUpperCase() === "BOOKED" && new Date(a.date).getTime() > now)
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const shown = upcoming.length ? upcoming : appointments.slice(0, APPOINTMENTS_PREVIEW);

  return (
    <section id="appointments">
      <DashCard>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-ink">{upcoming.length ? "Upcoming appointments" : "Appointments"}</h2>
          <CalendarDays className="h-5 w-5 text-violet-500" aria-hidden />
        </div>
        {shown.length === 0 ? (
          <p className="rounded-control border border-line bg-surface-soft p-3 text-sm text-ink-muted">You have no appointments yet.</p>
        ) : (
          <ul className="space-y-2.5">
            {shown.slice(0, APPOINTMENTS_PREVIEW).map((a) => (
              <li key={a.id} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">{a.doctor_name}</p>
                    <p className="mt-0.5 text-xs text-slate-500">{clinicDateTime(a.date)} PKT</p>
                  </div>
                  <Badge tone={TONE[a.status.toUpperCase()] ?? "neutral"}>{LABEL[a.status.toUpperCase()] ?? a.status.toLowerCase()}</Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
        <ButtonLink href="/doctors" className="mt-4 w-full" icon={<Stethoscope className="h-4 w-4" />}>
          Find a doctor and book
        </ButtonLink>
      </DashCard>
    </section>
  );
}
