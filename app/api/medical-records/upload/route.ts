import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

type UploadRecordBody = {
  title: string;
  fileName: string;
};

function isUploadRecordBody(value: unknown): value is UploadRecordBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return (
    typeof body.title === "string" &&
    typeof body.fileName === "string" &&
    body.title.trim().length > 0 &&
    body.fileName.trim().length > 0
  );
}

export async function POST(request: Request) {
  const auth = await requireUser(request, ["patient"]);
  if (auth instanceof Response) {
    return auth;
  }

  const userId = auth.user.id;
  const body: unknown = await request.json().catch(() => null);

  if (!isUploadRecordBody(body)) {
    return Response.json(
      { message: "Title and file name are required." },
      { status: 400 },
    );
  }

  const record = await prisma.medicalRecord.create({
    data: {
      userId,
      title: body.title.trim(),
      fileName: body.fileName.trim(),
      imageUrl: "",
    },
    select: {
      id: true,
      title: true,
      fileName: true,
      imageUrl: true,
      extractedText: true,
      scanStatus: true,
      createdAt: true,
    },
  });

  return Response.json(
    { message: "Medical record uploaded.", record },
    { status: 201 },
  );
}
