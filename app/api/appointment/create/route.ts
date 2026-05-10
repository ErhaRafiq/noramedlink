import { prisma } from "@/lib/prisma";
import { grantTemporaryDashboardAccessByOtp } from "@/lib/patient-access";

export const runtime = "nodejs";

type AppointmentBody = {
  doctorName: string;
  userId: number | string;
  patientAccessOtp?: string;
};

function isAppointmentBody(value: unknown): value is AppointmentBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return (
    typeof body.doctorName === "string" &&
    body.doctorName.trim().length > 0 &&
    (typeof body.userId === "number" || typeof body.userId === "string")
    && (typeof body.patientAccessOtp === "undefined" || typeof body.patientAccessOtp === "string")
  );
}

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);

  if (!isAppointmentBody(body)) {
    return Response.json(
      { message: "Doctor name and user ID are required." },
      { status: 400 },
    );
  }

  const userId = Number(body.userId);

  if (!Number.isInteger(userId) || userId <= 0) {
    return Response.json({ message: "Invalid user ID." }, { status: 400 });
  }

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true },
  });

  if (!user) {
    return Response.json({ message: "User not found." }, { status: 404 });
  }

  const assignedDoctor = await prisma.user.findFirst({
    where: {
      name: body.doctorName.trim(),
      role: "DOCTOR",
    },
    select: { id: true },
  });

  const appointment = await prisma.appointment.create({
    data: {
      doctorName: body.doctorName.trim(),
      doctorId: assignedDoctor?.id ?? null,
      userId,
      status: "BOOKED",
      paymentStatus: "PENDING",
    },
    select: {
      id: true,
      doctorName: true,
      doctorId: true,
      userId: true,
      date: true,
      status: true,
      paymentStatus: true,
    },
  });

  const patientAccessOtp =
    typeof body.patientAccessOtp === "string" ? body.patientAccessOtp.trim() : "";
  let dashboardAccessGranted = false;

  if (patientAccessOtp) {
    if (assignedDoctor) {
      const access = await grantTemporaryDashboardAccessByOtp({
        doctorId: assignedDoctor.id,
        otpCode: patientAccessOtp,
        expectedPatientId: userId,
      });

      dashboardAccessGranted = Boolean(access);
    }
  }

  return Response.json(
    {
      message: dashboardAccessGranted
        ? "Appointment booked and temporary dashboard access shared with the doctor."
        : "Appointment booked successfully.",
      appointment,
      dashboardAccessGranted,
    },
    { status: 201 },
  );
}
