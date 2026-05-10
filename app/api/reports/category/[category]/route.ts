import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { normalizeReportCategory } from "@/lib/patient-dashboard";
import { serializePatientReport } from "@/lib/patient-report-records";

export const runtime = "nodejs";

type Params = {
  params: Promise<{ category: string }>;
};

export async function GET(request: Request, context: Params) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const { category } = await context.params;
  const normalized = normalizeReportCategory(category);

  const reports = await prisma.patientReport.findMany({
    where: {
      patientId: session.user.id,
      OR: [
        { department: { name: { equals: normalized.charAt(0).toUpperCase() + normalized.slice(1), mode: "insensitive" } } },
        { title: { contains: normalized, mode: "insensitive" } },
      ],
    },
    include: { department: true },
    orderBy: { uploadDate: "desc" },
  });

  return Response.json(reports.map(serializePatientReport));
}
