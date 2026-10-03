import crypto from "node:crypto";

import { prisma } from "@/lib/prisma";

export type JwtPayload = {
  sub?: string;
  exp?: number;
  role?: string;
  email?: string;
  [key: string]: unknown;
};

export type Role = "patient" | "doctor" | "admin";

const ROLES: readonly Role[] = ["patient", "doctor", "admin"];

export type AuthenticatedUser = {
  id: number;
  name: string;
  email: string;
  phone: string;
  role: Role;
};

export type UserSession = {
  user: AuthenticatedUser;
  payload: JwtPayload;
};

function getJwtSecret() {
  const secret = process.env.JWT_SECRET_KEY || process.env.SECRET_KEY || process.env.NORA_JWT_SECRET;
  if (!secret) {
    throw new Error("JWT_SECRET_KEY is required to verify sessions.");
  }
  return secret;
}

function base64UrlDecode(value: string) {
  return Buffer.from(value, "base64url").toString("utf8");
}

export function verifyHs256Jwt(token: string): JwtPayload {
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new Error("Invalid authentication token.");
  }

  const [headerPart, payloadPart, signaturePart] = parts;
  const signingInput = `${headerPart}.${payloadPart}`;
  const expectedSignature = crypto
    .createHmac("sha256", getJwtSecret())
    .update(signingInput)
    .digest("base64url");

  const signature = Buffer.from(signaturePart);
  const expected = Buffer.from(expectedSignature);
  if (signature.length !== expected.length || !crypto.timingSafeEqual(signature, expected)) {
    throw new Error("Invalid authentication token.");
  }

  let payload: JwtPayload;
  try {
    payload = JSON.parse(base64UrlDecode(payloadPart)) as JwtPayload;
  } catch {
    throw new Error("Invalid authentication token.");
  }

  if (typeof payload.exp === "number" && payload.exp * 1000 <= Date.now()) {
    throw new Error("Session has expired.");
  }

  return payload;
}

export function extractBearerToken(request: Request) {
  const authorization = request.headers.get("authorization") ?? "";
  if (!authorization.toLowerCase().startsWith("bearer ")) {
    return null;
  }

  const token = authorization.slice(7).trim();
  return token.length > 0 ? token : null;
}

function normalizeRole(role: string): Role | null {
  const normalized = role.trim().toLowerCase();
  return (ROLES as readonly string[]).includes(normalized) ? (normalized as Role) : null;
}

function unauthorized(message: string) {
  return Response.json({ message }, { status: 401 });
}

function forbidden(message: string) {
  return Response.json({ message }, { status: 403 });
}

/**
 * Verifies the Bearer JWT and loads the user it names. The user ID comes only
 * from the verified token, never from query parameters or the request body.
 *
 * Returns the session, or a Response to return as-is:
 * 401 for a missing/invalid/expired token or unknown user,
 * 403 for an inactive account or a role outside `allowedRoles`.
 */
export async function requireUser(
  request: Request,
  allowedRoles?: readonly Role[],
): Promise<UserSession | Response> {
  const token = extractBearerToken(request);
  if (!token) {
    return unauthorized("Authentication token is required.");
  }

  let payload: JwtPayload;
  try {
    payload = verifyHs256Jwt(token);
  } catch (error) {
    return unauthorized(error instanceof Error ? error.message : "Invalid authentication token.");
  }

  const userId = Number(payload.sub);
  if (!Number.isInteger(userId) || userId <= 0) {
    return unauthorized("Invalid session.");
  }

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true, name: true, email: true, phone: true, role: true, isActive: true },
  });

  if (!user) {
    return unauthorized("Session not found.");
  }

  const role = normalizeRole(user.role);
  if (!role) {
    return forbidden("Account role is not recognised.");
  }

  if (!user.isActive) {
    return forbidden("Account is inactive.");
  }

  if (allowedRoles && !allowedRoles.includes(role)) {
    return forbidden(`${allowedRoles.map((r) => r[0].toUpperCase() + r.slice(1)).join(" or ")} access required.`);
  }

  return {
    user: { id: user.id, name: user.name, email: user.email, phone: user.phone, role },
    payload,
  };
}

/** True while the doctor holds an active, unexpired, unended grant to the patient's dashboard. */
export async function hasActiveDashboardAccess(doctorId: number, patientId: number) {
  const access = await prisma.patientDashboardAccess.findFirst({
    where: {
      doctorId,
      patientId,
      status: "ACTIVE",
      endedAt: null,
      OR: [{ expiresAt: null }, { expiresAt: { gt: new Date() } }],
    },
    select: { id: true },
  });

  return access !== null;
}
