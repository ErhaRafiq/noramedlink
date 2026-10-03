import { grantTemporaryDashboardAccessByOtp } from "@/lib/patient-access";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

type UnlockBody = {
  patientAccessOtp?: string;
};

export async function POST(request: Request) {
  const auth = await requireUser(request, ["doctor"]);
  if (auth instanceof Response) {
    return auth;
  }

  const doctorId = auth.user.id;
  const body = (await request.json().catch(() => null)) as UnlockBody | null;
  const patientAccessOtp = body?.patientAccessOtp?.trim() ?? "";

  if (!patientAccessOtp) {
    return Response.json({ message: "Patient dashboard OTP is required." }, { status: 400 });
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
