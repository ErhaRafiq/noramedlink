import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { parseNumber, serializeDailyVital } from "@/lib/patient-output";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body) {
    return Response.json({ message: "Vitals payload is required." }, { status: 400 });
  }

  const bloodPressureSystolic = parseNumber(body.bloodPressureSystolic);
  const bloodPressureDiastolic = parseNumber(body.bloodPressureDiastolic);
  const heartRate = parseNumber(body.heartRate);
  const spo2 = parseNumber(body.spo2);
  const temperature = parseNumber(body.temperature);
  const sugarLevel = body.sugarLevel === null || typeof body.sugarLevel === "undefined" ? null : parseNumber(body.sugarLevel);
  const weight = body.weight === null || typeof body.weight === "undefined" ? null : parseNumber(body.weight);
  const recordedAt = typeof body.recordedAt === "string" && body.recordedAt.trim() ? new Date(body.recordedAt) : new Date();

  if (
    bloodPressureSystolic === null ||
    bloodPressureDiastolic === null ||
    heartRate === null ||
    spo2 === null ||
    temperature === null ||
    Number.isNaN(recordedAt.getTime())
  ) {
    return Response.json({ message: "Valid systolic, diastolic, heart rate, SpO2, temperature, and time are required." }, { status: 400 });
  }

  const record = await prisma.$transaction(async (transaction) => {
    const created = await transaction.patientVital.create({
      data: {
        patientId: session.user.id,
        bloodPressureSystolic,
        bloodPressureDiastolic,
        heartRate,
        spo2,
        temperature,
        sugarLevel,
        weight,
        recordedAt,
      },
    });

    await transaction.vitals.create({
      data: {
        userId: session.user.id,
        bloodPressure: `${bloodPressureSystolic}/${bloodPressureDiastolic}`,
        sugarLevel: sugarLevel === null ? "Not recorded" : String(sugarLevel),
      },
    });

    return created;
  });

  return Response.json(serializeDailyVital(record), { status: 201 });
}
