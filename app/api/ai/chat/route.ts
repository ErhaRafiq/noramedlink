import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { answerPatientAssistant } from "@/lib/patient-ai";
import { buildMedicalDisclaimer } from "@/lib/patient-dashboard";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body || typeof body.message !== "string" || !body.message.trim()) {
    return Response.json({ message: "A question is required." }, { status: 400 });
  }

  const [reports, vitals, appointments, medicines] = await Promise.all([
    prisma.patientReport.findMany({
      where: { patientId: session.user.id },
      include: { department: true },
      orderBy: { uploadDate: "desc" },
      take: 5,
    }),
    prisma.patientVital.findMany({
      where: { patientId: session.user.id },
      orderBy: { recordedAt: "desc" },
      take: 3,
    }),
    prisma.appointment.findMany({
      where: { userId: session.user.id },
      orderBy: { date: "desc" },
      take: 3,
    }),
    prisma.medication.findMany({
      where: { OR: [{ userId: session.user.id }, { patientId: session.user.id }] },
      orderBy: { createdAt: "desc" },
      take: 5,
    }),
  ]);

  const context = [
    `Patient: ${session.user.name}`,
    `Reports: ${reports
      .map((report) => `${report.title} (${report.department?.name ?? "General"}): ${report.summary ?? report.extractedText ?? ""}`)
      .join("\n")}`,
    `Vitals: ${vitals
      .map(
        (vital) =>
          `${vital.recordedAt.toISOString()}: BP ${vital.bloodPressureSystolic}/${vital.bloodPressureDiastolic}, HR ${vital.heartRate}, SpO2 ${vital.spo2}, Temp ${vital.temperature}`,
      )
      .join("\n")}`,
    `Appointments: ${appointments.map((appointment) => `${appointment.doctorName} on ${appointment.date.toISOString()} (${appointment.status})`).join("\n")}`,
    `Medicines: ${medicines.map((medicine) => `${medicine.medicineName || medicine.name}: ${medicine.dosage}`).join("\n")}`,
  ]
    .filter(Boolean)
    .join("\n\n");

  const answer = await answerPatientAssistant({
    message: body.message.trim(),
    context,
    patientName: session.user.name,
  });

  return Response.json({
    answer: answer.answer || "I could not generate a response just now.",
    disclaimer: answer.disclaimer || buildMedicalDisclaimer(),
  });
}
