import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

type AddReminderBody = {
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
    typeof body.title === "string" &&
    typeof body.dueAt === "string" &&
    body.title.trim().length > 0 &&
    body.dueAt.trim().length > 0 &&
    (typeof body.fcmToken === "undefined" || typeof body.fcmToken === "string")
  );
}

export async function POST(request: Request) {
  const auth = await requireUser(request, ["patient"]);
  if (auth instanceof Response) {
    return auth;
  }

  const userId = auth.user.id;
  const body: unknown = await request.json().catch(() => null);

  if (!isAddReminderBody(body)) {
    return Response.json(
      { message: "Title and reminder time are required." },
      { status: 400 },
    );
  }

  const dueAt = new Date(body.dueAt);

  if (Number.isNaN(dueAt.getTime())) {
    return Response.json({ message: "Invalid reminder date." }, { status: 400 });
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
