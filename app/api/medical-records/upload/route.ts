import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

type UploadRecordBody = {
  userId: number | string;
  title: string;
  fileName: string;
};

function isUploadRecordBody(value: unknown): value is UploadRecordBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return (
    (typeof body.userId === "number" || typeof body.userId === "string") &&
    typeof body.title === "string" &&
    typeof body.fileName === "string" &&
    body.title.trim().length > 0 &&
    body.fileName.trim().length > 0
  );
}

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);

  if (!isUploadRecordBody(body)) {
    return Response.json(
      { message: "User ID, title, and file name are required." },
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
