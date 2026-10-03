import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

type EndAccessBody = {
  patientId?: number | string;
};

export async function POST(request: Request) {
  const auth = await requireUser(request, ["doctor"]);
  if (auth instanceof Response) {
    return auth;
  }

  const doctorId = auth.user.id;
  const body = (await request.json().catch(() => null)) as EndAccessBody | null;
  const patientId = Number(body?.patientId);

  if (!Number.isInteger(patientId) || patientId <= 0) {
    return Response.json({ message: "Valid patient user ID is required." }, { status: 400 });
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
