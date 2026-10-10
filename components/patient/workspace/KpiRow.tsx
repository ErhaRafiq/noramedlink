"use client";

import { ArrowRight, Bell, CalendarDays, CircleAlert, HeartPulse, Sparkles, Thermometer, Wifi } from "lucide-react";

import type { Appointment } from "@/lib/types";
import { formatDate, formatDateTime, formatTime, type NO_VITALS } from "./helpers";
import { DashCard, MiniVital } from "./ui";

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
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <DashCard>
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-blue-600">Today&apos;s Vitals</p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {vitalsRecordedAt ? `Recorded ${formatDateTime(vitalsRecordedAt)}` : "Nothing recorded today"}
            </p>
          </div>
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center shadow-md shadow-blue-200/40 flex-shrink-0">
            <HeartPulse className="h-4 w-4 text-white" />
          </div>
        </div>
        <div className="space-y-2.5">
          <MiniVital icon={HeartPulse} label="BP" value={vitals.bloodPressure} />
          <MiniVital icon={Wifi} label="Heart Rate" value={vitals.heartRate} />
          <MiniVital icon={Sparkles} label="SpO2" value={vitals.spo2} />
          <MiniVital icon={Thermometer} label="Temp" value={vitals.temperature} />
        </div>
        <button
          type="button"
          onClick={() => onNavigate("vitals")}
          className="mt-3 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition"
        >
          Add or view vitals <ArrowRight className="h-3 w-3" />
        </button>
      </DashCard>

      <DashCard>
        <div className="flex items-start justify-between">
          <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-md shadow-emerald-200/50">
            <Bell className="h-5 w-5 text-white" />
          </div>
          <ArrowRight className="h-4 w-4 text-slate-300 mt-1" />
        </div>
        <p className="mt-4 text-3xl font-black text-slate-900">{reminderCount}</p>
        <p className="text-sm font-semibold text-slate-500 mt-0.5">Active Reminders</p>
        <p className="text-xs text-slate-400 mt-0.5">Due today</p>
        <button
          type="button"
          onClick={() => onNavigate("reminders")}
          className="mt-3 text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center gap-1 transition"
        >
          View reminders <ArrowRight className="h-3 w-3" />
        </button>
      </DashCard>

      <DashCard>
        <div className="flex items-start justify-between">
          <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-md shadow-violet-200/50">
            <CalendarDays className="h-5 w-5 text-white" />
          </div>
          <ArrowRight className="h-4 w-4 text-slate-300 mt-1" />
        </div>
        {upcomingAppointment ? (
          <>
            <p className="mt-4 text-base font-black text-slate-900">{formatDate(upcomingAppointment.date)}</p>
            <p className="text-xs text-slate-500 mt-0.5">{formatTime(upcomingAppointment.date)}</p>
            <p className="text-sm font-semibold text-violet-700 mt-1">{upcomingAppointment.doctor_name}</p>
          </>
        ) : (
          <>
            <p className="mt-4 text-base font-black text-slate-900">No upcoming appointment</p>
            <p className="text-xs text-slate-500 mt-0.5">Book one with a verified doctor.</p>
          </>
        )}
        <button
          type="button"
          onClick={() => onNavigate("appointments")}
          className="mt-3 text-xs font-semibold text-violet-600 hover:text-violet-700 flex items-center gap-1 transition"
        >
          View all appointments <ArrowRight className="h-3 w-3" />
        </button>
      </DashCard>

      <DashCard>
        <div className="flex items-start justify-between">
          <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-rose-500 to-orange-500 flex items-center justify-center shadow-md shadow-rose-200/50">
            <CircleAlert className="h-5 w-5 text-white" />
          </div>
          <ArrowRight className="h-4 w-4 text-slate-300 mt-1" />
        </div>
        <p className="mt-4 text-3xl font-black text-slate-900">{criticalFlagCount}</p>
        <p className="text-sm font-semibold text-slate-500 mt-0.5">Critical Flags</p>
        <p className="text-xs text-slate-400 mt-0.5">Needs attention</p>
        <button
          type="button"
          onClick={() => onNavigate("insights")}
          className="mt-3 text-xs font-semibold text-rose-600 hover:text-rose-700 flex items-center gap-1 transition"
        >
          View details <ArrowRight className="h-3 w-3" />
        </button>
      </DashCard>
    </section>
  );
}
