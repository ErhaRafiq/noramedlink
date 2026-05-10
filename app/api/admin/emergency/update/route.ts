import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

const emergencyStatuses = new Set([
  "SEARCHING",
  "DOCTOR_ASSIGNED",
  "ON_THE_WAY",
  "COMPLETED",
  "CANCELLED",
]);

type UpdateEmergencyBody = {
  adminId?: number;
  bookingId?: number;
  status?: string;
  estimatedMinutes?: number;
};

async function requireAdmin(adminId: number) {
  const user = await prisma.user.findUnique({
    where: { id: adminId },
    select: { role: true },
  });

  return user?.role === "ADMIN";
}

export async function POST(request: Request) {
  const body = (await request.json()) as UpdateEmergencyBody;
  const adminId = Number(body.adminId);
  const bookingId = Number(body.bookingId);
  const status = body.status?.trim().toUpperCase();
  const estimatedMinutes = Number(body.estimatedMinutes);

  if (!Number.isInteger(adminId) || adminId <= 0) {
    return Response.json({ message: "Valid admin user ID is required." }, { status: 400 });
  }

  if (!(await requireAdmin(adminId))) {
    return Response.json({ message: "Admin access is required." }, { status: 403 });
  }

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
