import crypto from "node:crypto";

import { prisma } from "@/lib/prisma";

type JwtPayload = {
  sub?: string;
  exp?: number;
  role?: string;
  email?: string;
  [key: string]: unknown;
};

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

function getJwtSecret() {
  const secret = process.env.JWT_SECRET_KEY || process.env.SECRET_KEY || process.env.NORA_JWT_SECRET;
  if (!secret) {
    throw new Error("JWT_SECRET_KEY is required to verify patient sessions.");
  }
  return secret;
}

function base64UrlEncode(value: string) {
  return Buffer.from(value, "utf8").toString("base64url");
}

function base64UrlDecode(value: string) {
  return Buffer.from(value, "base64url").toString("utf8");
}

function verifyHs256Jwt(token: string): JwtPayload {
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

  const payload = JSON.parse(base64UrlDecode(payloadPart)) as JwtPayload;
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
