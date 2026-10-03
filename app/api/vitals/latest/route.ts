import { prisma } from "@/lib/prisma";
import { requireUser } from "@/lib/server-auth";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const auth = await requireUser(request, ["patient"]);
  if (auth instanceof Response) {
    return auth;
  }

  const vitals = await prisma.vitals.findFirst({
    where: { userId: auth.user.id },
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
