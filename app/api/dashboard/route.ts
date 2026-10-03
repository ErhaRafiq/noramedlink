import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const auth = await requireUser(request, ["patient"]);
  if (auth instanceof Response) {
    return auth;
  }

  const userId = auth.user.id;
  const now = new Date();
  const [
    latestVitals,
    vitalsHistory,
    upcomingAppointment,
    medications,
    reminders,
    medicalRecords,
  ] = await Promise.all([
    prisma.vitals.findFirst({
      where: { userId },
      orderBy: { createdAt: "desc" },
      select: {
        id: true,
        bloodPressure: true,
        sugarLevel: true,
        createdAt: true,
      },
    }),
    prisma.vitals.findMany({
      where: { userId },
      orderBy: { createdAt: "desc" },
      take: 5,
      select: {
        id: true,
        bloodPressure: true,
        sugarLevel: true,
        createdAt: true,
      },
    }),
    prisma.appointment.findFirst({
      where: {
        userId,
        date: { gte: now },
      },
      orderBy: { date: "asc" },
      select: {
        id: true,
        doctorName: true,
        date: true,
      },
    }),
    prisma.medication.findMany({
      where: { userId },
      orderBy: { createdAt: "desc" },
      select: {
        id: true,
        name: true,
        dosage: true,
        status: true,
        createdAt: true,
      },
    }),
    prisma.reminder.findMany({
      where: {
        userId,
        dueAt: { gte: now },
      },
      orderBy: { dueAt: "asc" },
      take: 5,
      select: {
        id: true,
        title: true,
        dueAt: true,
        status: true,
      },
    }),
    prisma.medicalRecord.findMany({
      where: { userId },
      orderBy: { createdAt: "desc" },
      select: {
        id: true,
        title: true,
        fileName: true,
        imageUrl: true,
        extractedText: true,
        scanStatus: true,
        createdAt: true,
      },
    }),
  ]);

  return Response.json({
    latestVitals,
    vitalsHistory,
    upcomingAppointment,
    medications,
    reminders,
    medicalRecords,
  });
}
