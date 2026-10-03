import { prisma } from "@/lib/prisma";
import { extractBearerToken, verifyHs256Jwt, type JwtPayload } from "@/lib/server-auth";

export { extractBearerToken };

type PatientSession = {
  user: {
    id: number;
    name: string;
    email: string;
    role: string;
    phone: string;
  };
  payload: JwtPayload;
};

export async function requirePatientSession(request: Request): Promise<PatientSession> {
  const token = extractBearerToken(request);
  if (!token) {
    throw new Error("Authentication token is required.");
  }

  const payload = verifyHs256Jwt(token);
  const userId = Number(payload.sub);
  if (!Number.isInteger(userId) || userId <= 0) {
    throw new Error("Invalid patient session.");
  }

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      name: true,
      email: true,
      role: true,
      phone: true,
    },
  });

  if (!user) {
    throw new Error("Patient session not found.");
  }

  if (user.role !== "PATIENT") {
    throw new Error("Patient access required.");
  }

  return { user, payload };
}

export async function resolvePatientSession(request: Request) {
  try {
    return await requirePatientSession(request);
  } catch (error) {
    return Response.json(
      { message: error instanceof Error ? error.message : "Authentication failed." },
      { status: 401 },
    );
  }
}

export function mapUserToAuthUser(user: { id: number; name: string; email: string; role: string; phone: string }) {
  return {
    id: user.id,
    full_name: user.name,
    email: user.email,
    role: user.role.toLowerCase(),
    phone: user.phone,
    is_email_verified: true,
    is_identity_verified: true,
    verification_status: "verified",
  };
}
