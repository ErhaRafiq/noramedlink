import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

const paymentStatuses = new Set([
  "PENDING",
  "SUCCESS",
  "FAILED",
  "REFUNDED",
  "PAY_ON_VISIT",
]);

type UpdatePaymentBody = {
  adminId?: number;
  paymentId?: number;
  status?: string;
};

async function requireAdmin(adminId: number) {
  const user = await prisma.user.findUnique({
    where: { id: adminId },
    select: { role: true },
  });

  return user?.role === "ADMIN";
}

export async function POST(request: Request) {
  const body = (await request.json()) as UpdatePaymentBody;
  const adminId = Number(body.adminId);
  const paymentId = Number(body.paymentId);
  const status = body.status?.trim().toUpperCase();

  if (!Number.isInteger(adminId) || adminId <= 0) {
    return Response.json({ message: "Valid admin user ID is required." }, { status: 400 });
  }

  if (!(await requireAdmin(adminId))) {
    return Response.json({ message: "Admin access is required." }, { status: 403 });
  }

  if (!Number.isInteger(paymentId) || paymentId <= 0) {
    return Response.json({ message: "Valid payment ID is required." }, { status: 400 });
  }

  if (!status || !paymentStatuses.has(status)) {
    return Response.json({ message: "Valid payment status is required." }, { status: 400 });
  }

  const payment = await prisma.payment.update({
    where: { id: paymentId },
    data: { status },
    select: {
      id: true,
      appointmentId: true,
      amount: true,
      method: true,
      purpose: true,
      status: true,
      reference: true,
    },
  });

  if (payment.appointmentId) {
    await prisma.appointment.update({
      where: { id: payment.appointmentId },
      data: { paymentStatus: status },
    });
  }

  return Response.json({ message: "Payment status updated.", payment });
}
