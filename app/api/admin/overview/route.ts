import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const auth = await requireUser(request, ["admin"]);
  if (auth instanceof Response) {
    return auth;
  }

  const [
    users,
    appointments,
    emergencyBookings,
    payments,
    totalPatients,
    totalDoctors,
    totalAdmins,
  ] = await Promise.all([
    prisma.user.findMany({
      orderBy: { id: "desc" },
      take: 12,
      select: { id: true, name: true, email: true, role: true },
    }),
    prisma.appointment.findMany({
      orderBy: { date: "desc" },
      take: 20,
      select: { id: true, doctorName: true, userId: true, date: true },
    }),
    prisma.emergencyBooking.findMany({
      orderBy: { createdAt: "desc" },
      take: 20,
      select: {
        id: true,
        userId: true,
        patientName: true,
        phone: true,
        address: true,
        symptoms: true,
        doctorName: true,
        status: true,
        estimatedMinutes: true,
        createdAt: true,
      },
    }),
    prisma.payment.findMany({
      orderBy: { createdAt: "desc" },
      take: 20,
      select: {
        id: true,
        userId: true,
        appointmentId: true,
        amount: true,
        method: true,
        purpose: true,
        status: true,
        phone: true,
        reference: true,
        createdAt: true,
      },
    }),
    prisma.user.count({ where: { role: "PATIENT" } }),
    prisma.user.count({ where: { role: "DOCTOR" } }),
    prisma.user.count({ where: { role: "ADMIN" } }),
  ]);

  const userNameById = new Map(users.map((user) => [user.id, user.name]));
  const totalPaymentAmount = payments.reduce((sum, payment) => sum + payment.amount, 0);

  return Response.json({
    stats: {
      totalPatients,
      totalDoctors,
      totalAdmins,
      appointmentCount: appointments.length,
      emergencyBookingCount: emergencyBookings.length,
      paymentCount: payments.length,
      totalPaymentAmount,
    },
    users,
    appointments: appointments.map((appointment) => ({
      ...appointment,
      patientName: userNameById.get(appointment.userId) ?? `User #${appointment.userId}`,
    })),
    emergencyBookings,
    payments: payments.map((payment) => ({
      ...payment,
      patientName: userNameById.get(payment.userId) ?? `User #${payment.userId}`,
    })),
  });
}
