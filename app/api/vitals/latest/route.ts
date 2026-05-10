import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const userId = Number(searchParams.get("userId"));

  if (!Number.isInteger(userId) || userId <= 0) {
    return Response.json({ message: "Valid user ID is required." }, { status: 400 });
  }

  const vitals = await prisma.vitals.findFirst({
    where: { userId },
    orderBy: { createdAt: "desc" },
    select: {
      id: true,
      userId: true,
      bloodPressure: true,
      sugarLevel: true,
      createdAt: true,
    },
  });

  return Response.json({ vitals });
}
