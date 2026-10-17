import {
  AlarmClock,
  AlertTriangle,
  BadgeCheck,
  Bell,
  CalendarCheck2,
  CalendarClock,
  CalendarX2,
  ClipboardList,
  Eye,
  KeyRound,
  Pill,
  Star,
  Stethoscope,
  Undo2,
  Wallet,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { NotificationCategory } from "@/lib/types";

export const CATEGORY_LABEL: Record<NotificationCategory, string> = {
  appointments: "Appointments",
  payments: "Payments",
  records: "Health records",
  account: "Account",
  admin: "Admin",
};

type Look = { icon: LucideIcon; tone: string };

// One look per kind of notification: an icon and the colours of its round badge (unread uses these; read is muted).
const LOOKS: Record<string, Look> = {
  appointment_confirmed: { icon: CalendarCheck2, tone: "bg-blue-50 text-blue-700" },
  appointment_rescheduled: { icon: CalendarClock, tone: "bg-amber-50 text-amber-700" },
  appointment_cancelled: { icon: CalendarX2, tone: "bg-rose-50 text-rose-700" },
  appointment_missed: { icon: CalendarX2, tone: "bg-rose-50 text-rose-700" },
  appointment_reminder: { icon: AlarmClock, tone: "bg-teal-50 text-teal-700" },
  appointment_completed: { icon: Star, tone: "bg-amber-50 text-amber-700" },
  review_received: { icon: Star, tone: "bg-amber-50 text-amber-700" },
  payment_received: { icon: Wallet, tone: "bg-emerald-50 text-emerald-700" },
  payment_refunded: { icon: Undo2, tone: "bg-emerald-50 text-emerald-700" },
  payment_refund: { icon: Undo2, tone: "bg-blue-50 text-blue-700" },
  prescription_added: { icon: Pill, tone: "bg-violet-50 text-violet-700" },
  prescription_cancelled: { icon: Pill, tone: "bg-rose-50 text-rose-700" },
  access_opened: { icon: Eye, tone: "bg-violet-50 text-violet-700" },
  record_changed: { icon: ClipboardList, tone: "bg-violet-50 text-violet-700" },
  account_password: { icon: KeyRound, tone: "bg-slate-100 text-slate-700" },
  doctor_approved: { icon: BadgeCheck, tone: "bg-emerald-50 text-emerald-700" },
  doctor_rejected: { icon: XCircle, tone: "bg-rose-50 text-rose-700" },
  doctor_pmdc: { icon: BadgeCheck, tone: "bg-emerald-50 text-emerald-700" },
  admin_doctor_review: { icon: Stethoscope, tone: "bg-blue-50 text-blue-700" },
  admin_refund_attention: { icon: AlertTriangle, tone: "bg-rose-50 text-rose-700" },
};

export function lookOf(kind: string): Look {
  return LOOKS[kind] ?? { icon: Bell, tone: "bg-slate-100 text-slate-600" };
}

/** "Just now", "5 min ago", "3 h ago", then the date: always worked out from the real time of the notification. */
export function relativeTime(iso: string, now = Date.now()): string {
  const then = new Date(iso).getTime();
  const seconds = Math.round((now - then) / 1000);
  if (seconds < 45) return "Just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return new Intl.DateTimeFormat("en", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }).format(new Date(iso));
}

const dayKey = (date: Date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;

/** "Today", "Yesterday" or the date, for the heading above a group. */
export function dayLabel(iso: string, now = new Date()): string {
  const date = new Date(iso);
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (dayKey(date) === dayKey(now)) return "Today";
  if (dayKey(date) === dayKey(yesterday)) return "Yesterday";
  return new Intl.DateTimeFormat("en", { weekday: "long", day: "numeric", month: "long" }).format(date);
}

/** Items (already newest first) in runs of the same day, each with its heading. */
export function groupByDay<T extends { at: string }>(items: T[], now = new Date()): { label: string; items: T[] }[] {
  const groups: { label: string; items: T[] }[] = [];
  for (const item of items) {
    const label = dayLabel(item.at, now);
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.items.push(item);
    else groups.push({ label, items: [item] });
  }
  return groups;
}

/** Fired by code that has just caused a notification (a booking, a payment): the bell checks at once. */
export const NOTIFICATIONS_CHANGED_EVENT = "nora:notifications-changed";

export function requestNotificationRefresh() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT));
}
