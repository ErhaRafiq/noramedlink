import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

const emergencyStatuses = new Set([
  "SEARCHING",
  "DOCTOR_ASSIGNED",
  "ON_THE_WAY",
  "COMPLETED",
  "CANCELLED",
]);

type UpdateEmergencyBody = {
  bookingId?: number;
  status?: string;
  estimatedMinutes?: number;
};

export async function POST(request: Request) {
  const auth = await requireUser(request, ["admin"]);
  if (auth instanceof Response) {
    return auth;
  }

  const body = (await request.json().catch(() => ({}))) as UpdateEmergencyBody;
  const bookingId = Number(body.bookingId);
  const status = body.status?.trim().toUpperCase();
  const estimatedMinutes = Number(body.estimatedMinutes);

  if (!Number.isInteger(bookingId) || bookingId <= 0) {
    return Response.json({ message: "Valid booking ID is required." }, { status: 400 });
  }

  if (!status || !emergencyStatuses.has(status)) {
    return Response.json({ message: "Valid emergency status is required." }, { status: 400 });
  }

  const booking = await prisma.emergencyBooking.update({
    where: { id: bookingId },
    data: {
      status,
      ...(Number.isInteger(estimatedMinutes) && estimatedMinutes > 0
        ? { estimatedMinutes }
        : {}),
    },
    select: {
      id: true,
      patientName: true,
      phone: true,
      status: true,
      estimatedMinutes: true,
    },
  });

  return Response.json({ message: "Emergency booking updated.", booking });
}
