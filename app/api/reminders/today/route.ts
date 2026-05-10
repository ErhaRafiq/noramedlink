import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { computeReminderDisplayStatus } from "@/lib/patient-reminders";
import { serializeReminder } from "@/lib/patient-output";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const now = new Date();
  const startOfDay = new Date(now);
  startOfDay.setHours(0, 0, 0, 0);
  const endOfDay = new Date(now);
  endOfDay.setHours(23, 59, 59, 999);

  const reminders = await prisma.medicineReminder.findMany({
    where: {
      patientId: session.user.id,
      reminderTime: {
        gte: startOfDay,
        lte: endOfDay,
      },
    },
    include: {
      medication: true,
    },
    orderBy: { reminderTime: "asc" },
  });

  const normalized = reminders.map((reminder) => {
    const status = computeReminderDisplayStatus({
      reminderTime: reminder.reminderTime,
      takenAt: reminder.takenAt,
      skippedAt: reminder.skippedAt,
      now,
    });

    return status === reminder.status
      ? reminder
      : { ...reminder, status };
  });

  const updates = normalized
    .filter((reminder) => reminder.status !== reminders.find((original) => original.id === reminder.id)?.status)
    .map((reminder) =>
      prisma.medicineReminder.update({
        where: { id: reminder.id },
        data: { status: reminder.status },
      }),
    );

  if (updates.length > 0) {
    await prisma.$transaction(updates).catch(() => null);
  }

  return Response.json(normalized.map(serializeReminder));
}
