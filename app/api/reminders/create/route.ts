import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { computeReminderDisplayStatus } from "@/lib/patient-reminders";
import { serializeReminder } from "@/lib/patient-output";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body) {
    return Response.json({ message: "Reminder details are required." }, { status: 400 });
  }

  const medicationId = typeof body.medicationId === "number" ? body.medicationId : Number(body.medicationId);
  const reminderTimeRaw = typeof body.reminderTime === "string" ? body.reminderTime.trim() : "";
  const frequency = typeof body.frequency === "string" ? body.frequency.trim() : "";

  if (!Number.isInteger(medicationId) || medicationId <= 0 || !reminderTimeRaw || !frequency) {
    return Response.json(
      { message: "Medication, reminder time, and frequency are required." },
      { status: 400 },
    );
  }

  const reminderTime = new Date(reminderTimeRaw);
  if (Number.isNaN(reminderTime.getTime())) {
    return Response.json({ message: "Invalid reminder time." }, { status: 400 });
  }

  const medication = await prisma.medication.findFirst({
    where: {
      id: medicationId,
      OR: [{ userId: session.user.id }, { patientId: session.user.id }],
    },
  });

  if (!medication) {
    return Response.json({ message: "Medication not found." }, { status: 404 });
  }

  const status = computeReminderDisplayStatus({ reminderTime });
  const reminder = await prisma.medicineReminder.create({
    data: {
      medicationId: medication.id,
      patientId: session.user.id,
      reminderTime,
      frequency,
      status,
      logs: {
        create: {
          patientId: session.user.id,
          scheduledFor: reminderTime,
          status,
        },
      },
    },
    include: {
      medication: true,
    },
  });

  await prisma.notification.create({
    data: {
      userId: session.user.id,
      title: "Medicine reminder scheduled",
      body: `${medication.medicineName} reminder set for ${reminderTime.toISOString()}`,
      status: "SCHEDULED",
      scheduledFor: reminderTime,
      reminderId: reminder.id,
    },
  }).catch(() => null);

  return Response.json(serializeReminder(reminder), { status: 201 });
}
