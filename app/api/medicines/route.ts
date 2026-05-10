import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { serializeMedication } from "@/lib/patient-output";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const medications = await prisma.medication.findMany({
    where: {
      OR: [{ userId: session.user.id }, { patientId: session.user.id }],
    },
    orderBy: { createdAt: "desc" },
  });

  return Response.json(medications.map(serializeMedication));
}

export async function POST(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body) {
    return Response.json({ message: "Medication details are required." }, { status: 400 });
  }

  const medicineName = typeof body.medicineName === "string" ? body.medicineName.trim() : "";
  const dosage = typeof body.dosage === "string" ? body.dosage.trim() : "";
  const instructions = typeof body.instructions === "string" ? body.instructions.trim() : null;
  const startDateValue = typeof body.startDate === "string" ? body.startDate : "";
  const endDateValue = typeof body.endDate === "string" ? body.endDate : "";

  if (!medicineName || !dosage || !startDateValue) {
    return Response.json(
      { message: "Medicine name, dosage, and start date are required." },
      { status: 400 },
    );
  }

  const startDate = new Date(startDateValue);
  const endDate = endDateValue ? new Date(endDateValue) : null;
  if (Number.isNaN(startDate.getTime()) || (endDateValue && Number.isNaN(endDate?.getTime() ?? Number.NaN))) {
    return Response.json({ message: "Invalid medicine dates." }, { status: 400 });
  }

  const medication = await prisma.medication.create({
    data: {
      userId: session.user.id,
      patientId: session.user.id,
      name: medicineName,
      medicineName,
      dosage,
      instructions,
      startDate,
      endDate,
      status: "ACTIVE",
    },
  });

  return Response.json(serializeMedication(medication), { status: 201 });
}
