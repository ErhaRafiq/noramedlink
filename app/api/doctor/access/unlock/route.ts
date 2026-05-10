import { prisma } from "@/lib/prisma";
import { grantTemporaryDashboardAccessByOtp } from "@/lib/patient-access";

export const runtime = "nodejs";

type UnlockBody = {
  doctorId?: number | string;
  patientAccessOtp?: string;
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as UnlockBody | null;
  const doctorId = Number(body?.doctorId);
  const patientAccessOtp = body?.patientAccessOtp?.trim() ?? "";

  if (!Number.isInteger(doctorId) || doctorId <= 0) {
    return Response.json({ message: "Valid doctor user ID is required." }, { status: 400 });
  }

  if (!patientAccessOtp) {
    return Response.json({ message: "Patient dashboard OTP is required." }, { status: 400 });
  }

  const doctor = await prisma.user.findUnique({
    where: { id: doctorId },
    select: { role: true },
  });

  if (doctor?.role !== "DOCTOR") {
    return Response.json({ message: "Doctor access is required." }, { status: 403 });
  }

  const access = await grantTemporaryDashboardAccessByOtp({
    doctorId,
    otpCode: patientAccessOtp,
  });

  if (!access) {
    return Response.json({ message: "Invalid or expired patient dashboard OTP." }, { status: 404 });
  }

  return Response.json({
    message: `Temporary dashboard access unlocked for ${access.patient.name}.`,
    patient: access.patient,
    expiresAt: access.expiresAt,
  });
}
