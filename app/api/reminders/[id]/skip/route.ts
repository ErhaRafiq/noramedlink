import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { serializeReminder } from "@/lib/patient-output";

export const runtime = "nodejs";

type Params = {
  params: Promise<{ id: string }>;
};

export async function PATCH(request: Request, context: Params) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const { id } = await context.params;
  const reminderId = Number(id);
  if (!Number.isInteger(reminderId) || reminderId <= 0) {
    return Response.json({ message: "Reminder not found." }, { status: 404 });
  }

  const reminder = await prisma.medicineReminder.findFirst({
    where: { id: reminderId, patientId: session.user.id },
    include: { medication: true },
  });

  if (!reminder) {
    return Response.json({ message: "Reminder not found." }, { status: 404 });
  }

  const updated = await prisma.medicineReminder.update({
    where: { id: reminderId },
    data: {
      status: "SKIPPED",
      skippedAt: new Date(),
    },
    include: { medication: true },
  });

  await prisma.reminderLog.create({
    data: {
      reminderId: updated.id,
      patientId: session.user.id,
      scheduledFor: updated.reminderTime,
      status: "SKIPPED",
    },
  }).catch(() => null);

  return Response.json(serializeReminder(updated));
}
