/** Value for <input type="datetime-local"> in the browser's local time: "2026-10-11T10:00". */
export function toDateTimeInputValue(date: Date) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Tomorrow at 10:00 local time: a sensible default for a new appointment. */
export function tomorrowAtTen() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(10, 0, 0, 0);
  return toDateTimeInputValue(date);
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}


/** The clinic's time zone (Pakistan, UTC+5 all year): the days and times patients book are in it. */
export const CLINIC_TIME_ZONE = "Asia/Karachi";

/** "Mon 12 Oct" for a moment, in clinic time. */
export function clinicDay(value: string | Date) {
  return new Intl.DateTimeFormat("en", { weekday: "short", day: "numeric", month: "short", timeZone: CLINIC_TIME_ZONE }).format(new Date(value));
}

/** "4:30 PM" for a moment, in clinic time. */
export function clinicTime(value: string | Date) {
  return new Intl.DateTimeFormat("en", { hour: "numeric", minute: "2-digit", timeZone: CLINIC_TIME_ZONE }).format(new Date(value));
}

/** "Mon 12 Oct, 4:30 PM" in clinic time. */
export function clinicDateTime(value: string | Date) {
  return `${clinicDay(value)}, ${clinicTime(value)}`;
}
