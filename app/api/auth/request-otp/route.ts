export const runtime = "nodejs";

export function POST() {
  return Response.json(
    {
      message: "OTP signup is disabled for now. Use direct signup instead.",
    },
    { status: 410 },
  );
}
