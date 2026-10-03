import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

type DeleteRecordBody = {
  recordId: number | string;
};

function isDeleteRecordBody(value: unknown): value is DeleteRecordBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return typeof body.recordId === "number" || typeof body.recordId === "string";
}

export async function POST(request: Request) {
  const auth = await requireUser(request, ["patient"]);
  if (auth instanceof Response) {
    return auth;
  }

  const userId = auth.user.id;
  const body: unknown = await request.json().catch(() => null);

  if (!isDeleteRecordBody(body)) {
    return Response.json(
      { message: "Report ID is required." },
      { status: 400 },
    );
  }

  const recordId = Number(body.recordId);

  if (!Number.isInteger(recordId) || recordId <= 0) {
    return Response.json({ message: "Invalid report ID." }, { status: 400 });
  }

  // Scoped to the signed-in patient: another patient's record is reported as not found.
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
