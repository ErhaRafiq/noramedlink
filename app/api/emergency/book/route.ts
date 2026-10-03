import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

type EmergencyBody = {
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
  const auth = await requireUser(request, ["patient"]);
  if (auth instanceof Response) {
    return auth;
  }

  const userId = auth.user.id;
  const body: unknown = await request.json().catch(() => null);

  if (!isEmergencyBody(body)) {
    return Response.json(
      { message: "Patient name, phone, address, and symptoms are required." },
      { status: 400 },
    );
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
