import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";

export const runtime = "nodejs";

const demoDoctors = [
  { id: 9001, name: "Dr. Ayesha Khan", specialty: "Cardiology", hospitalName: "Nora MedLink Clinic", rating: 4.9, availableToday: true, source: "demo" as const },
  { id: 9002, name: "Dr. Hassan Ali", specialty: "Internal Medicine", hospitalName: "Nora MedLink Clinic", rating: 4.8, availableToday: true, source: "demo" as const },
  { id: 9003, name: "Dr. Saba Ahmed", specialty: "Endocrinology", hospitalName: "Nora MedLink Clinic", rating: 4.7, availableToday: false, source: "demo" as const },
  { id: 9004, name: "Dr. Omar Farooq", specialty: "Orthopedics", hospitalName: "Nora MedLink Clinic", rating: 4.8, availableToday: true, source: "demo" as const },
];

export async function GET(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const doctors = await prisma.user.findMany({
    where: {
      role: "DOCTOR",
      doctorProfile: { isNot: null },
      isActive: true,
    },
    include: {
      doctorProfile: true,
    },
    orderBy: { createdAt: "desc" },
    take: 50,
  });

  const response = doctors.map((doctor, index) => ({
    id: doctor.id,
    name: doctor.name,
    specialty: doctor.doctorProfile?.specialization ?? "General Medicine",
    hospitalName: doctor.doctorProfile?.hospitalName ?? "Nora MedLink Clinic",
    rating: Number((4.7 + (index % 4) * 0.1).toFixed(1)),
    availableToday: index % 2 === 0,
    source: "registered" as const,
  }));

  return Response.json(response.length > 0 ? response : demoDoctors);
}
