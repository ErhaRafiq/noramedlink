import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { serializeAppointment } from "@/lib/patient-output";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const appointments = await prisma.appointment.findMany({
    where: { userId: session.user.id },
    orderBy: { date: "asc" },
  });

  return Response.json(appointments.map(serializeAppointment));
}
