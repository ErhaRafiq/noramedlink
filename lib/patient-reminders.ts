export type ReminderDisplayStatus = "UPCOMING" | "DUE_NOW" | "TAKEN" | "MISSED" | "SKIPPED";

export function computeReminderDisplayStatus({
  reminderTime,
  takenAt,
  skippedAt,
  now = new Date(),
}: {
  reminderTime: Date;
  takenAt?: Date | null;
  skippedAt?: Date | null;
  now?: Date;
}): ReminderDisplayStatus {
  if (takenAt) {
    return "TAKEN";
  }
  if (skippedAt) {
    return "SKIPPED";
  }

  const diffMs = reminderTime.getTime() - now.getTime();
  if (diffMs <= -30 * 60 * 1000) {
    return "MISSED";
  }
  if (diffMs <= 0) {
    return "DUE_NOW";
  }
  if (diffMs <= 30 * 60 * 1000) {
    return "UPCOMING";
  }
  return "UPCOMING";
}

export function reconcileReminderStatus({
  reminderTime,
  status,
  takenAt,
  skippedAt,
  now = new Date(),
}: {
  reminderTime: Date;
  status: string;
  takenAt?: Date | null;
  skippedAt?: Date | null;
  now?: Date;
}) {
  if (status === "TAKEN" || takenAt) {
    return "TAKEN";
  }
  if (status === "SKIPPED" || skippedAt) {
    return "SKIPPED";
  }

  const diffMs = reminderTime.getTime() - now.getTime();
  if (diffMs <= -30 * 60 * 1000) {
    return "MISSED";
  }
  if (diffMs <= 0) {
    return "DUE_NOW";
  }
  if (diffMs <= 30 * 60 * 1000) {
    return "UPCOMING";
  }
  if (diffMs > 30 * 60 * 1000) {
    return "UPCOMING";
  }
  return status || "UPCOMING";
}
