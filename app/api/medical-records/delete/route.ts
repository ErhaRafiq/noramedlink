import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

type DeleteRecordBody = {
  recordId: number | string;
  userId: number | string;
};

function isDeleteRecordBody(value: unknown): value is DeleteRecordBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return (
    (typeof body.userId === "number" || typeof body.userId === "string") &&
    (typeof body.recordId === "number" || typeof body.recordId === "string")
  );
}

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);

  if (!isDeleteRecordBody(body)) {
    return Response.json(
      { message: "User ID and report ID are required." },
      { status: 400 },
    );
  }

  const userId = Number(body.userId);
  const recordId = Number(body.recordId);

  if (!Number.isInteger(userId) || userId <= 0) {
    return Response.json({ message: "Invalid user ID." }, { status: 400 });
  }

  if (!Number.isInteger(recordId) || recordId <= 0) {
    return Response.json({ message: "Invalid report ID." }, { status: 400 });
  }

  const record = await prisma.medicalRecord.findFirst({
    where: { id: recordId, userId },
    select: { id: true, title: true },
  });

  if (!record) {
    return Response.json({ message: "Report not found." }, { status: 404 });
  }

  await prisma.medicalRecord.delete({
    where: { id: record.id },
  });

  return Response.json({
    message: "Report removed from medical tiles.",
    record,
  });
}
