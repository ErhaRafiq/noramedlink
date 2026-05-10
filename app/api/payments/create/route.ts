import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

const walletMethods = ["JAZZCASH", "EASYPAISA", "NAYAPAY"] as const;
const paymentMethods = [...walletMethods, "CARD", "RAAST", "CASH"] as const;

type PaymentBody = {
  userId: number | string;
  amount: number | string;
  method: string;
  purpose: string;
  phone?: string;
  appointmentId?: number | string;
};

function isPaymentBody(value: unknown): value is PaymentBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return (
    (typeof body.userId === "number" || typeof body.userId === "string") &&
    (typeof body.amount === "number" || typeof body.amount === "string") &&
    typeof body.method === "string" &&
    typeof body.purpose === "string" &&
    body.purpose.trim().length > 0 &&
    (typeof body.phone === "undefined" || typeof body.phone === "string") &&
    (typeof body.appointmentId === "undefined" ||
      typeof body.appointmentId === "number" ||
      typeof body.appointmentId === "string")
  );
}

function createReference() {
  return `NML-${Date.now()}-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
}

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);

  if (!isPaymentBody(body)) {
    return Response.json(
      { message: "User, amount, payment method, and purpose are required." },
      { status: 400 },
    );
  }

  const userId = Number(body.userId);
  const amount = Number(body.amount);
  const method = body.method.trim().toUpperCase();

  if (!Number.isInteger(userId) || userId <= 0) {
    return Response.json({ message: "Invalid user ID." }, { status: 400 });
  }

  if (!Number.isInteger(amount) || amount < 1) {
    return Response.json({ message: "Invalid payment amount." }, { status: 400 });
  }

  if (!paymentMethods.includes(method as (typeof paymentMethods)[number])) {
    return Response.json({ message: "Unsupported payment method." }, { status: 400 });
  }

  const phone = typeof body.phone === "string" ? body.phone.trim() : "";
  const appointmentId =
    typeof body.appointmentId === "undefined" ? null : Number(body.appointmentId);

  if (walletMethods.includes(method as (typeof walletMethods)[number]) && !phone) {
    return Response.json({ message: "Phone number is required for wallet payments." }, { status: 400 });
  }

  if (appointmentId !== null && (!Number.isInteger(appointmentId) || appointmentId <= 0)) {
    return Response.json({ message: "Invalid appointment ID." }, { status: 400 });
  }

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true },
  });

  if (!user) {
    return Response.json({ message: "User not found." }, { status: 404 });
  }

  const appointment =
    appointmentId === null
      ? null
      : await prisma.appointment.findFirst({
          where: {
            id: appointmentId,
            userId,
          },
          select: { id: true, doctorName: true, date: true },
        });

  if (appointmentId !== null && !appointment) {
    return Response.json({ message: "Appointment not found for this user." }, { status: 404 });
  }

  const payment = await prisma.payment.create({
    data: {
      userId,
      appointmentId: appointment?.id ?? null,
      amount,
      method,
      purpose: body.purpose.trim(),
      phone: phone || null,
      reference: createReference(),
      status: walletMethods.includes(method as (typeof walletMethods)[number])
        ? "SUCCESS"
        : method === "CASH"
          ? "PAY_ON_VISIT"
          : "PENDING",
      invoiceNumber: `INV-${Date.now()}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`,
    },
    select: {
      id: true,
      appointmentId: true,
      amount: true,
      method: true,
      purpose: true,
      status: true,
      phone: true,
      reference: true,
      invoiceNumber: true,
      createdAt: true,
    },
  });

  if (appointment && payment.status === "SUCCESS") {
    await prisma.appointment.update({
      where: { id: appointment.id },
      data: { paymentStatus: "SUCCESS" },
    });
  }

  return Response.json(
    {
      message:
        payment.status === "SUCCESS" && walletMethods.includes(method as (typeof walletMethods)[number])
          ? `Payment successful via ${method === "NAYAPAY" ? "NayaPay" : method === "JAZZCASH" ? "JazzCash" : "Easypaisa"}.`
          : payment.status === "PAY_ON_VISIT"
            ? "Cash payment will be collected on visit."
            : "Payment request created.",
      payment,
      appointment,
    },
    { status: 201 },
  );
}
