import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

type AddVitalsBody = {
  userId: number | string;
  bloodPressure: string;
  sugarLevel: string;
};

function isAddVitalsBody(value: unknown): value is AddVitalsBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return (
    (typeof body.userId === "number" || typeof body.userId === "string") &&
    typeof body.bloodPressure === "string" &&
    typeof body.sugarLevel === "string" &&
    body.bloodPressure.trim().length > 0 &&
    body.sugarLevel.trim().length > 0
  );
}

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);

  if (!isAddVitalsBody(body)) {
    return Response.json(
      { message: "User ID, blood pressure, and sugar level are required." },
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

  const vitals = await prisma.vitals.create({
    data: {
      userId,
      bloodPressure: body.bloodPressure.trim(),
      sugarLevel: body.sugarLevel.trim(),
    },
    select: {
      id: true,
      userId: true,
      bloodPressure: true,
      sugarLevel: true,
      createdAt: true,
    },
  });

  return Response.json(
    { message: "Vitals added successfully.", vitals },
    { status: 201 },
  );
}
