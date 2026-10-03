import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

const paymentStatuses = new Set([
  "PENDING",
  "SUCCESS",
  "FAILED",
  "REFUNDED",
  "PAY_ON_VISIT",
]);

type UpdatePaymentBody = {
  paymentId?: number;
  status?: string;
};

export async function POST(request: Request) {
  const auth = await requireUser(request, ["admin"]);
  if (auth instanceof Response) {
    return auth;
  }

  const body = (await request.json().catch(() => ({}))) as UpdatePaymentBody;
  const paymentId = Number(body.paymentId);
  const status = body.status?.trim().toUpperCase();

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
