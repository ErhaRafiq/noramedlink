import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

function parseDoctorId(request: Request) {
  const { searchParams } = new URL(request.url);
  const doctorId = Number(searchParams.get("userId"));

  return Number.isInteger(doctorId) && doctorId > 0 ? doctorId : null;
}

export async function GET(request: Request) {
  const doctorId = parseDoctorId(request);
  const now = new Date();

  if (!doctorId) {
    return Response.json({ message: "Valid doctor user ID is required." }, { status: 400 });
  }

  const doctor = await prisma.user.findUnique({
    where: { id: doctorId },
    select: { id: true, name: true, email: true, role: true },
  });

  if (!doctor) {
    return Response.json({ message: "Doctor account not found." }, { status: 404 });
  }

  if (doctor.role !== "DOCTOR") {
    return Response.json({ message: "Doctor access is required." }, { status: 403 });
  }

  const [appointments, emergencyBookings, dashboardAccesses] = await Promise.all([
    prisma.appointment.findMany({
      where: { doctorName: doctor.name },
      orderBy: { date: "desc" },
      take: 30,
      select: { id: true, doctorName: true, userId: true, date: true },
    }),
    prisma.emergencyBooking.findMany({
      where: { doctorName: doctor.name },
      orderBy: { createdAt: "desc" },
      take: 12,
      select: {
        id: true,
        userId: true,
        patientName: true,
        phone: true,
        address: true,
        symptoms: true,
        status: true,
        estimatedMinutes: true,
        createdAt: true,
      },
    }),
    prisma.patientDashboardAccess.findMany({
      where: {
        doctorId,
        status: "ACTIVE",
        endedAt: null,
        OR: [{ expiresAt: null }, { expiresAt: { gt: now } }],
      },
      orderBy: { createdAt: "desc" },
      select: { patientId: true, createdAt: true, expiresAt: true },
    }),
  ]);

  const appointmentPatientIds = [
    ...new Set([
      ...appointments.map((appointment) => appointment.userId),
      ...emergencyBookings.map((booking) => booking.userId),
    ]),
  ];
  const accessPatientIds = [...new Set(dashboardAccesses.map((access) => access.patientId))];
  const allVisiblePatientIds = [...new Set([...appointmentPatientIds, ...accessPatientIds])];

  const [patients, latestVitals, medicalRecords, medications] = await Promise.all([
    prisma.user.findMany({
      where: { id: { in: allVisiblePatientIds } },
      select: { id: true, name: true, email: true },
    }),
    Promise.all(
      accessPatientIds.map((userId) =>
        prisma.vitals.findFirst({
          where: { userId },
          orderBy: { createdAt: "desc" },
          select: {
            userId: true,
            bloodPressure: true,
            sugarLevel: true,
            createdAt: true,
          },
        }),
      ),
    ),
    prisma.medicalRecord.findMany({
      where: { userId: { in: accessPatientIds } },
      orderBy: { createdAt: "desc" },
      take: 40,
      select: {
        id: true,
        userId: true,
        title: true,
        fileName: true,
        scanStatus: true,
        extractedText: true,
        createdAt: true,
      },
    }),
    prisma.medication.findMany({
      where: { userId: { in: accessPatientIds } },
      orderBy: { createdAt: "desc" },
      take: 30,
      select: {
        id: true,
        userId: true,
        name: true,
        dosage: true,
        status: true,
        createdAt: true,
      },
    }),
  ]);

  const patientNameById = new Map(patients.map((patient) => [patient.id, patient.name]));
  const patientEmailById = new Map(patients.map((patient) => [patient.id, patient.email]));
  const accessPatientIdSet = new Set(accessPatientIds);
  const accessExpiresAtByPatientId = new Map(
    dashboardAccesses.map((access) => [access.patientId, access.expiresAt]),
  );
  const vitalsByUserId = new Map(
    latestVitals
      .filter((vitals): vitals is NonNullable<typeof vitals> => vitals !== null)
      .map((vitals) => [vitals.userId, vitals]),
  );
  const recordCountByUserId = medicalRecords.reduce<Map<number, number>>((counts, record) => {
    counts.set(record.userId, (counts.get(record.userId) ?? 0) + 1);
    return counts;
  }, new Map());

  const patientSummaries = accessPatientIds.map((userId) => ({
    id: userId,
    name: patientNameById.get(userId) ?? `Patient #${userId}`,
    email: patientEmailById.get(userId) ?? "",
    latestVitals: vitalsByUserId.get(userId) ?? null,
    recordCount: recordCountByUserId.get(userId) ?? 0,
    appointmentCount: appointments.filter((appointment) => appointment.userId === userId).length,
    accessExpiresAt: accessExpiresAtByPatientId.get(userId) ?? null,
  }));

  return Response.json({
    doctor,
    stats: {
      appointments: appointments.length,
      patients: accessPatientIds.length,
      emergencyBookings: emergencyBookings.length,
      medicalRecords: medicalRecords.length,
      medications: medications.length,
    },
    appointments: appointments.map((appointment) => ({
      ...appointment,
      patientName: patientNameById.get(appointment.userId) ?? `Patient #${appointment.userId}`,
      patientEmail: patientEmailById.get(appointment.userId) ?? "",
      hasDashboardAccess: accessPatientIdSet.has(appointment.userId),
      accessExpiresAt: accessExpiresAtByPatientId.get(appointment.userId) ?? null,
    })),
    emergencyBookings: emergencyBookings.map((booking) => ({
      ...booking,
      hasDashboardAccess: accessPatientIdSet.has(booking.userId),
      accessExpiresAt: accessExpiresAtByPatientId.get(booking.userId) ?? null,
    })),
    patients: patientSummaries,
    medicalRecords: medicalRecords.map((record) => ({
      ...record,
      patientName: patientNameById.get(record.userId) ?? `Patient #${record.userId}`,
    })),
    medications: medications.map((medication) => ({
      ...medication,
      patientName: patientNameById.get(medication.userId) ?? `Patient #${medication.userId}`,
    })),
  });
}
