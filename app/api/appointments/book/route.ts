import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { serializeAppointment } from "@/lib/patient-output";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body) {
    return Response.json({ message: "Booking details are required." }, { status: 400 });
  }

  const doctorId = typeof body.doctorId === "number" ? body.doctorId : Number(body.doctorId);
  const doctorName = typeof body.doctorName === "string" ? body.doctorName.trim() : "";
  const specialty = typeof body.specialty === "string" ? body.specialty.trim() : "";
  const date = typeof body.date === "string" ? body.date.trim() : "";
  const time = typeof body.time === "string" ? body.time.trim() : "";
  const reason = typeof body.reason === "string" ? body.reason.trim() : "";

  if (!Number.isInteger(doctorId) || doctorId <= 0 || !doctorName || !specialty || !date || !time || !reason) {
    return Response.json(
      { message: "Doctor, specialty, date, time, and reason are required." },
      { status: 400 },
    );
  }

  const appointmentDate = new Date(`${date}T${time}`);
  if (Number.isNaN(appointmentDate.getTime())) {
    return Response.json({ message: "Appointment slot is missing or invalid." }, { status: 400 });
  }

  const doctor = await prisma.user.findFirst({
    where: {
      id: doctorId,
      role: "DOCTOR",
    },
    select: { id: true },
  });

  const appointment = await prisma.appointment.create({
    data: {
      userId: session.user.id,
      doctorId: doctor?.id ?? null,
      doctorName,
      specialty,
      reason,
      date: appointmentDate,
      status: "BOOKED",
      paymentStatus: "PENDING",
      notes: reason,
    },
  });

  return Response.json(
    {
      message: "Appointment booked successfully.",
      appointment: serializeAppointment(appointment),
    },
    { status: 201 },
  );
}
