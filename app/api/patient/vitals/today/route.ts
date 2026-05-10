import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { parseBloodPressure, serializeDailyVital } from "@/lib/patient-output";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const latest = await prisma.patientVital.findFirst({
    where: { patientId: session.user.id },
    orderBy: { recordedAt: "desc" },
  });

  if (latest) {
    return Response.json(serializeDailyVital(latest));
  }

  const legacy = await prisma.vitals.findFirst({
    where: { userId: session.user.id },
    orderBy: { createdAt: "desc" },
    select: {
      id: true,
      userId: true,
      bloodPressure: true,
      sugarLevel: true,
      createdAt: true,
    },
  });

  if (!legacy) {
    return Response.json(null);
  }

  const parsed = parseBloodPressure(legacy.bloodPressure);
  if (!parsed) {
    return Response.json(null);
  }

  return Response.json({
    id: legacy.id,
    patient_id: legacy.userId,
    blood_pressure_systolic: parsed.systolic,
    blood_pressure_diastolic: parsed.diastolic,
    heart_rate: 72,
    spo2: 98,
    temperature: 98.4,
    sugar_level: Number.parseFloat(legacy.sugarLevel) || null,
    weight: null,
    recorded_at: legacy.createdAt.toISOString(),
    created_at: legacy.createdAt.toISOString(),
  });
}
