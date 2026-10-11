"use client";

import type { ReactNode } from "react";
import { ArrowRight, Bell, CalendarDays, CircleAlert, HeartPulse, Sparkles, Thermometer, Wifi, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";
import type { Appointment } from "@/lib/types";
import { formatDate, formatDateTime, formatTime, type NO_VITALS } from "./helpers";
import { DashCard, MiniVital } from "./ui";

function KpiCard({
  icon: Icon,
  tint,
  label,
  children,
  action,
  onAction,
}: {
  icon: LucideIcon;
  tint: string;
  label: string;
  children: ReactNode;
  action: string;
  onAction: () => void;
}) {
  return (
    <DashCard className="flex flex-col">
      <div className="flex items-center gap-3">
        <span className={cn("grid h-9 w-9 place-items-center rounded-control", tint)}>
          <Icon className="h-4 w-4" aria-hidden />
        </span>
        <p className="text-sm font-medium text-ink-muted">{label}</p>
      </div>
      <div className="mt-4 flex-1">{children}</div>
      <button type="button" onClick={onAction} className="mt-4 inline-flex items-center gap-1 self-start text-xs font-semibold text-brand-blue hover:underline">
        {action} <ArrowRight className="h-3 w-3" aria-hidden />
      </button>
    </DashCard>
  );
}

export function KpiRow({
  vitals,
  vitalsRecordedAt,
  reminderCount,
  upcomingAppointment,
  criticalFlagCount,
  onNavigate,
}: {
  vitals: typeof NO_VITALS;
  vitalsRecordedAt: string | null;
  reminderCount: number;
  upcomingAppointment: Appointment | null;
  criticalFlagCount: number;
  onNavigate: (id: string) => void;
}) {
  return (
    <section aria-label="Overview" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard icon={HeartPulse} tint="bg-blue-50 text-brand-blue" label="Today's vitals" action="Add or view vitals" onAction={() => onNavigate("vitals")}>
        <div className="space-y-2">
          <MiniVital icon={HeartPulse} label="Blood pressure" value={vitals.bloodPressure} />
          <MiniVital icon={Wifi} label="Heart rate" value={vitals.heartRate} />
          <MiniVital icon={Sparkles} label="SpO2" value={vitals.spo2} />
          <MiniVital icon={Thermometer} label="Temperature" value={vitals.temperature} />
        </div>
        <p className="mt-3 text-xs text-ink-muted">{vitalsRecordedAt ? `Recorded ${formatDateTime(vitalsRecordedAt)}` : "Nothing recorded today"}</p>
      </KpiCard>

      <KpiCard icon={Bell} tint="bg-emerald-50 text-emerald-700" label="Medicines today" action="See today's schedule" onAction={() => onNavigate("medications")}>
        <p className="text-3xl font-semibold text-ink">{reminderCount}</p>
        <p className="mt-1 text-sm text-ink-muted">{reminderCount === 1 ? "reminder scheduled" : "reminders scheduled"}</p>
      </KpiCard>

      <KpiCard icon={CalendarDays} tint="bg-violet-50 text-violet-700" label="Next appointment" action="Appointments" onAction={() => onNavigate("appointments")}>
        {upcomingAppointment ? (
          <>
            <p className="text-base font-semibold text-ink">{formatDate(upcomingAppointment.date)}</p>
            <p className="text-sm text-ink-muted">{formatTime(upcomingAppointment.date)}</p>
            <p className="mt-1 truncate text-sm font-medium text-violet-700">{upcomingAppointment.doctor_name}</p>
          </>
        ) : (
          <>
            <p className="text-base font-semibold text-ink">None booked</p>
            <p className="text-sm text-ink-muted">Book with a verified doctor.</p>
          </>
        )}
      </KpiCard>

      <KpiCard icon={CircleAlert} tint="bg-rose-50 text-rose-600" label="Flags to review" action="See health flags" onAction={() => onNavigate("insights")}>
        <p className="text-3xl font-semibold text-ink">{criticalFlagCount}</p>
        <p className="mt-1 text-sm text-ink-muted">
          {criticalFlagCount === 0 ? "nothing flagged as high risk" : "high-risk results to discuss with a doctor"}
        </p>
      </KpiCard>
    </section>
  );
}
