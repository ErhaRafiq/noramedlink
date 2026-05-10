import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

type AddReminderBody = {
  userId: number | string;
  title: string;
  dueAt: string;
  fcmToken?: string;
};

function isAddReminderBody(value: unknown): value is AddReminderBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return (
    (typeof body.userId === "number" || typeof body.userId === "string") &&
    typeof body.title === "string" &&
    typeof body.dueAt === "string" &&
    body.title.trim().length > 0 &&
    body.dueAt.trim().length > 0 &&
    (typeof body.fcmToken === "undefined" || typeof body.fcmToken === "string")
  );
}

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);

  if (!isAddReminderBody(body)) {
    return Response.json(
      { message: "User ID, title, and reminder time are required." },
      { status: 400 },
    );
  }

  const userId = Number(body.userId);
  const dueAt = new Date(body.dueAt);

  if (!Number.isInteger(userId) || userId <= 0) {
    return Response.json({ message: "Invalid user ID." }, { status: 400 });
  }

  if (Number.isNaN(dueAt.getTime())) {
    return Response.json({ message: "Invalid reminder date." }, { status: 400 });
  }

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true },
  });

  if (!user) {
    return Response.json({ message: "User not found." }, { status: 404 });
  }

  const reminder = await prisma.reminder.create({
    data: {
      userId,
      title: body.title.trim(),
      dueAt,
      status: "UPCOMING",
      fcmToken: body.fcmToken?.trim() || null,
      notifications: {
        create: {
          userId,
          title: body.title.trim(),
          body: `Reminder scheduled for ${dueAt.toISOString()}`,
          status: "SCHEDULED",
          scheduledFor: dueAt,
        },
      },
    },
    select: {
      id: true,
      userId: true,
      title: true,
      dueAt: true,
      status: true,
      fcmToken: true,
      createdAt: true,
    },
  });

  return Response.json(
    { message: "Reminder saved successfully.", reminder },
    { status: 201 },
  );
}
