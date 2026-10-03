import { createPatientDashboardOtp } from "@/lib/patient-access";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const auth = await requireUser(request, ["patient"]);
  if (auth instanceof Response) {
    return auth;
  }

  const otp = await createPatientDashboardOtp(auth.user.id);

  if (!otp) {
    return Response.json({ message: "Patient account is required to generate an OTP." }, { status: 403 });
  }

  return Response.json({
    message: "One-time dashboard OTP generated.",
    otp,
  });
}
