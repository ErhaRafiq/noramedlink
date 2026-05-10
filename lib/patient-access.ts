import { prisma } from "@/lib/prisma";

const otpLifetimeMinutes = 15;
const consultationLifetimeHours = 2;

function createOtpCode() {
  return String(Math.floor(100000 + Math.random() * 900000));
}

function addMinutes(date: Date, minutes: number) {
  return new Date(date.getTime() + minutes * 60 * 1000);
}

function addHours(date: Date, hours: number) {
  return new Date(date.getTime() + hours * 60 * 60 * 1000);
}

export async function createPatientDashboardOtp(patientId: number) {
  const patient = await prisma.user.findUnique({
    where: { id: patientId },
    select: { id: true, role: true },
  });

  if (patient?.role !== "PATIENT") {
    return null;
  }

  await prisma.patientDashboardOtp.updateMany({
    where: {
      patientId,
      usedAt: null,
      expiresAt: { gt: new Date() },
    },
    data: {
      usedAt: new Date(),
    },
  });

  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      const expiresAt = addMinutes(new Date(), otpLifetimeMinutes);

      return await prisma.patientDashboardOtp.create({
        data: {
          patientId,
          code: createOtpCode(),
          expiresAt,
        },
        select: {
          code: true,
          expiresAt: true,
        },
      });
    } catch {
      // Retry if the generated six-digit OTP collides with an existing code.
    }
  }

  throw new Error("Unable to create patient dashboard OTP.");
}

export async function grantTemporaryDashboardAccessByOtp({
  doctorId,
  otpCode,
  expectedPatientId,
}: {
  doctorId: number;
  otpCode: string;
  expectedPatientId?: number;
}) {
  const now = new Date();
  const normalizedCode = otpCode.trim();
  const otp = await prisma.patientDashboardOtp.findFirst({
    where: {
      code: normalizedCode,
      usedAt: null,
      expiresAt: { gt: now },
      ...(expectedPatientId ? { patientId: expectedPatientId } : {}),
    },
    select: {
      id: true,
      patientId: true,
    },
  });

  if (!otp) {
    return null;
  }

  const patient = await prisma.user.findFirst({
    where: {
      id: otp.patientId,
      role: "PATIENT",
    },
    select: { id: true, name: true, email: true },
  });

  if (!patient) {
    return null;
  }

  const expiresAt = addHours(now, consultationLifetimeHours);

  await prisma.$transaction([
    prisma.patientDashboardOtp.update({
      where: { id: otp.id },
      data: { usedAt: now },
    }),
    prisma.patientDashboardAccess.upsert({
      where: {
        doctorId_patientId: {
          doctorId,
          patientId: patient.id,
        },
      },
      update: {
        status: "ACTIVE",
        expiresAt,
        endedAt: null,
      },
      create: {
        doctorId,
        patientId: patient.id,
        status: "ACTIVE",
        expiresAt,
      },
    }),
  ]);

  return {
    patient,
    expiresAt,
  };
}
