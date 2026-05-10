import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { serializeVitalTrend } from "@/lib/patient-output";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const records = await prisma.patientVital.findMany({
    where: { patientId: session.user.id },
    orderBy: { recordedAt: "desc" },
    take: 14,
  });

  return Response.json(records.map(serializeVitalTrend).reverse());
}
