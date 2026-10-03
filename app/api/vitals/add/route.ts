import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

type AddVitalsBody = {
  bloodPressure: string;
  sugarLevel: string;
};

function isAddVitalsBody(value: unknown): value is AddVitalsBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return (
    typeof body.bloodPressure === "string" &&
    typeof body.sugarLevel === "string" &&
    body.bloodPressure.trim().length > 0 &&
    body.sugarLevel.trim().length > 0
  );
}

export async function POST(request: Request) {
  const auth = await requireUser(request, ["patient"]);
  if (auth instanceof Response) {
    return auth;
  }

  const userId = auth.user.id;
  const body: unknown = await request.json().catch(() => null);

  if (!isAddVitalsBody(body)) {
    return Response.json(
      { message: "Blood pressure and sugar level are required." },
      { status: 400 },
    );
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
