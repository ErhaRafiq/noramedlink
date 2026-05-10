import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

function parseUserId(request: Request) {
  const { searchParams } = new URL(request.url);
  const userId = Number(searchParams.get("userId"));

  return Number.isInteger(userId) && userId > 0 ? userId : null;
}

export async function GET(request: Request) {
  const userId = parseUserId(request);

  if (!userId) {
    return Response.json({ message: "Valid user ID is required." }, { status: 400 });
  }

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true },
  });

  if (!user) {
    return Response.json({ message: "User not found." }, { status: 404 });
  }

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
