import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { serializePatientReport } from "@/lib/patient-report-records";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const reports = await prisma.patientReport.findMany({
    where: { patientId: session.user.id },
    include: { department: true },
    orderBy: { uploadDate: "desc" },
  });

  return Response.json(reports.map(serializePatientReport));
}
