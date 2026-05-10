import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

type EndAccessBody = {
  doctorId?: number | string;
  patientId?: number | string;
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as EndAccessBody | null;
  const doctorId = Number(body?.doctorId);
  const patientId = Number(body?.patientId);

  if (!Number.isInteger(doctorId) || doctorId <= 0) {
    return Response.json({ message: "Valid doctor user ID is required." }, { status: 400 });
  }

  if (!Number.isInteger(patientId) || patientId <= 0) {
    return Response.json({ message: "Valid patient user ID is required." }, { status: 400 });
  }

  const doctor = await prisma.user.findUnique({
    where: { id: doctorId },
    select: { role: true },
  });

  if (doctor?.role !== "DOCTOR") {
    return Response.json({ message: "Doctor access is required." }, { status: 403 });
  }

  await prisma.patientDashboardAccess.updateMany({
    where: {
      doctorId,
      patientId,
      status: "ACTIVE",
    },
    data: {
      status: "ENDED",
      endedAt: new Date(),
    },
  });

  return Response.json({ message: "Consultation session ended. Patient dashboard access is closed." });
}
