import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

type EmergencyBody = {
  userId: number | string;
  patientName: string;
  phone: string;
  address: string;
  symptoms: string;
  latitude?: number | string;
  longitude?: number | string;
};

const emergencyDoctors = [
  "Dr. Ayesha Khan",
  "Dr. Bilal Siddiqui",
  "Dr. Sara Ahmed",
  "Dr. Usman Raza",
];

function isEmergencyBody(value: unknown): value is EmergencyBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return (
    (typeof body.userId === "number" || typeof body.userId === "string") &&
    typeof body.patientName === "string" &&
    typeof body.phone === "string" &&
    typeof body.address === "string" &&
    typeof body.symptoms === "string" &&
    body.patientName.trim().length > 0 &&
    body.phone.trim().length > 0 &&
    body.address.trim().length > 0 &&
    body.symptoms.trim().length > 0
  );
}

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);

  if (!isEmergencyBody(body)) {
    return Response.json(
      { message: "Patient name, phone, address, symptoms, and user ID are required." },
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

  const latitude = body.latitude === undefined ? null : Number(body.latitude);
  const longitude = body.longitude === undefined ? null : Number(body.longitude);
  const doctorName =
    emergencyDoctors[Math.floor(Math.random() * emergencyDoctors.length)];

  const booking = await prisma.emergencyBooking.create({
    data: {
      userId,
      patientName: body.patientName.trim(),
      phone: body.phone.trim(),
      address: body.address.trim(),
      symptoms: body.symptoms.trim(),
      doctorName,
      status: "DOCTOR_ASSIGNED",
      estimatedMinutes: 18,
      latitude: Number.isFinite(latitude) ? latitude : null,
      longitude: Number.isFinite(longitude) ? longitude : null,
    },
    select: {
      id: true,
      doctorName: true,
      status: true,
      estimatedMinutes: true,
      createdAt: true,
    },
  });

  return Response.json(
    {
      message: `${doctorName} is assigned for your home visit.`,
      booking,
    },
    { status: 201 },
  );
}
