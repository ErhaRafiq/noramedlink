import {
  BookOpen,
  Bone,
  ClipboardList,
  Dumbbell,
  FileText,
  HeartPulse,
  Pill,
  Sparkles,
} from "lucide-react";

import {
  buildMedicalDisclaimer,
  normalizeReportCategory,
  REPORT_CATEGORIES,
  type ReportCategoryId,
} from "@/lib/patient-dashboard";
import type { Appointment, DailyVital, MedicalDocument, MedicineReminder } from "@/lib/types";

export const DISCLAIMER = buildMedicalDisclaimer();

// How many items the dashboard lists before "View all".
export const REPORTS_PREVIEW = 6;
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

const CATEGORY_GRADIENTS: Record<ReportCategoryId, string> = {
  heart: "from-rose-400 via-fuchsia-500 to-indigo-500",
  liver: "from-amber-400 via-orange-500 to-rose-500",
  kidney: "from-cyan-400 via-sky-500 to-blue-500",
  blood: "from-red-400 via-rose-500 to-orange-500",
  diabetes: "from-emerald-400 via-teal-500 to-cyan-500",
  ortho: "from-slate-300 via-slate-400 to-slate-500",
  prescriptions: "from-violet-400 via-fuchsia-500 to-pink-500",
  general: "from-blue-400 via-indigo-500 to-cyan-500",
};

export function getCategoryMeta(category: string) {
  const normalized = normalizeReportCategory(category);
  const meta = REPORT_CATEGORIES.find((e) => e.id === normalized) ?? REPORT_CATEGORIES[REPORT_CATEGORIES.length - 1];
  return { ...meta, style: { gradient: CATEGORY_GRADIENTS[normalized] } };
}

export function categoryIcon(category: string) {
  const n = normalizeReportCategory(category);
  if (n === "heart") return <HeartPulse className="h-4 w-4" />;
  if (n === "liver") return <BookOpen className="h-4 w-4" />;
  if (n === "kidney") return <Dumbbell className="h-4 w-4" />;
  if (n === "blood") return <ClipboardList className="h-4 w-4" />;
  if (n === "diabetes") return <Sparkles className="h-4 w-4" />;
  if (n === "ortho") return <Bone className="h-4 w-4" />;
  if (n === "prescriptions") return <Pill className="h-4 w-4" />;
  return <FileText className="h-4 w-4" />;
}

/** Report count per category, in the fixed category order. */
export function countReportsByCategory(reports: MedicalDocument[]) {
  const counts = new Map<string, number>();
  for (const r of reports) {
    const cat = normalizeReportCategory(r.category);
    counts.set(cat, (counts.get(cat) ?? 0) + 1);
  }
  return REPORT_CATEGORIES.map((cat) => ({ ...cat, count: counts.get(cat.id) ?? 0 }));
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
