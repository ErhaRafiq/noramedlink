import { Bone, Droplets, FileText, FlaskConical, HeartPulse, Pill } from "lucide-react";

import { departmentLabel, toDepartmentSlug, type DepartmentSlug } from "@/lib/departments";
import { buildMedicalDisclaimer } from "@/lib/patient-dashboard";
import type { Appointment, DailyVital, MedicineReminder } from "@/lib/types";

export const DISCLAIMER = buildMedicalDisclaimer();

// How many risk flags the dashboard lists before "View all".
export const RISKS_PREVIEW = 4;

// Shown when nothing has been recorded. Never fill in typical values as if they were the patient's.
export const NO_VITALS = {
  bloodPressure: "Not recorded",
  heartRate: "Not recorded",
  spo2: "Not recorded",
  temperature: "Not recorded",
};

export function formatDateTime(value?: string | null) {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function formatDate(value?: string | null) {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}

export function formatTime(value: string) {
  return new Date(value).toLocaleTimeString("en", { hour: "2-digit", minute: "2-digit" });
}

export function formatVitalCardValue(vital: DailyVital | null) {
  if (!vital) return NO_VITALS;
  return {
    bloodPressure: `${vital.blood_pressure_systolic}/${vital.blood_pressure_diastolic} mmHg`,
    heartRate: vital.heart_rate === null ? NO_VITALS.heartRate : `${vital.heart_rate} bpm`,
    spo2: vital.spo2 === null ? NO_VITALS.spo2 : `${vital.spo2}%`,
    temperature: vital.temperature === null ? NO_VITALS.temperature : `${vital.temperature.toFixed(1)}°F`,
  };
}

export function isToday(value: string) {
  return new Date(value).toDateString() === new Date().toDateString();
}

export function getUpcomingAppointment(appointments: Appointment[]) {
  const now = Date.now();
  return (
    appointments
      .filter((a) => new Date(a.date).getTime() >= now)
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())[0] ?? null
  );
}

const DEPARTMENT_GRADIENTS: Record<DepartmentSlug, string> = {
  heart: "from-rose-400 via-fuchsia-500 to-indigo-500",
  kidney: "from-cyan-400 via-sky-500 to-blue-500",
  ortho: "from-slate-300 via-slate-400 to-slate-500",
  lab: "from-red-400 via-rose-500 to-orange-500",
  medicine: "from-violet-400 via-fuchsia-500 to-pink-500",
  general: "from-blue-400 via-indigo-500 to-cyan-500",
};

/** Label and colour for a report's department (unknown values fall back to General). */
export function getDepartmentMeta(department: string | null | undefined) {
  const slug = toDepartmentSlug(department);
  return { slug, label: departmentLabel(slug), gradient: DEPARTMENT_GRADIENTS[slug] };
}

export function departmentIcon(department: string | null | undefined) {
  const slug = toDepartmentSlug(department);
  if (slug === "heart") return <HeartPulse className="h-4 w-4" />;
  if (slug === "kidney") return <Droplets className="h-4 w-4" />;
  if (slug === "ortho") return <Bone className="h-4 w-4" />;
  if (slug === "lab") return <FlaskConical className="h-4 w-4" />;
  if (slug === "medicine") return <Pill className="h-4 w-4" />;
  return <FileText className="h-4 w-4" />;
}

export function getReminderDisplay(reminder: MedicineReminder) {
  const diffMs = new Date(reminder.reminder_time).getTime() - Date.now();
  if (reminder.status === "TAKEN") return { label: "Taken", tone: "bg-emerald-50 text-emerald-700 border border-emerald-100" };
  if (reminder.status === "SKIPPED") return { label: "Skipped", tone: "bg-slate-100 text-slate-700 border border-slate-200" };
  if (reminder.status === "MISSED" || diffMs <= -30 * 60 * 1000)
    return { label: "Missed", tone: "bg-rose-100 text-rose-800 border border-rose-200" };
  if (diffMs <= 0) return { label: "Due now", tone: "bg-rose-50 text-rose-700 border border-rose-100" };
  if (diffMs <= 30 * 60 * 1000) return { label: "Upcoming in 30 min", tone: "bg-amber-50 text-amber-700 border border-amber-100" };
  return { label: "Upcoming", tone: "bg-blue-50 text-blue-700 border border-blue-100" };
}

export function isReminderPending(reminder: MedicineReminder) {
  const { label } = getReminderDisplay(reminder);
  return label === "Due now" || label === "Upcoming in 30 min" || label === "Upcoming";
}

export function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}
