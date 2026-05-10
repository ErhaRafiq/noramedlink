import { createPatientDashboardOtp } from "@/lib/patient-access";

export const runtime = "nodejs";

type OtpBody = {
  userId?: number | string;
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as OtpBody | null;
  const userId = Number(body?.userId);

  if (!Number.isInteger(userId) || userId <= 0) {
    return Response.json({ message: "Valid patient user ID is required." }, { status: 400 });
  }

  const otp = await createPatientDashboardOtp(userId);

  if (!otp) {
    return Response.json({ message: "Patient account is required to generate an OTP." }, { status: 403 });
  }

  return Response.json({
    message: "One-time dashboard OTP generated.",
    otp,
  });
}
