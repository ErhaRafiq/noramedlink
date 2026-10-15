import { createHmac } from "node:crypto";

import { backendBaseUrl } from "@/lib/backend-url";

/**
 * Server-only session handling. The browser never holds a token: the access and refresh tokens live
 * in HttpOnly cookies set here, and this server adds them to the calls it forwards to FastAPI.
 * (Imported only by route handlers under app/api.)
 */
export const ACCESS_COOKIE = "nora_at";
export const REFRESH_COOKIE = "nora_rt";
const COOKIE_SECONDS = 7 * 24 * 3600; // the refresh token's life; the access token inside expires sooner

export type Tokens = { access_token: string; refresh_token: string };

export function readCookies(request: Request): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of (request.headers.get("cookie") ?? "").split(";")) {
    const index = part.indexOf("=");
    if (index > 0) out[part.slice(0, index).trim()] = decodeURIComponent(part.slice(index + 1).trim());
  }
  return out;
}

function serialize(name: string, value: string, maxAge: number) {
  const secure = process.env.NODE_ENV === "production" ? "; Secure" : "";
  return `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; HttpOnly; SameSite=Lax${secure}`;
}

/** Set-Cookie values that sign the browser in. */
export function sessionCookies(tokens: Tokens) {
  return [serialize(ACCESS_COOKIE, tokens.access_token, COOKIE_SECONDS), serialize(REFRESH_COOKIE, tokens.refresh_token, COOKIE_SECONDS)];
}

/** Set-Cookie values that sign the browser out. */
export function clearedCookies() {
  return [serialize(ACCESS_COOKIE, "", 0), serialize(REFRESH_COOKIE, "", 0)];
}

export function withCookies(response: Response, cookies: string[]) {
  for (const cookie of cookies) response.headers.append("Set-Cookie", cookie);
  return response;
}

/** Proof, for FastAPI, that this call comes from our own server (so the client address we forward can be trusted). */
function proxyProof() {
  const secret = process.env.JWT_SECRET_KEY;
  return secret ? createHmac("sha256", secret).update("nora-medlink-proxy-v1").digest("hex") : null;
}

/** Headers every call to FastAPI carries: the real client address, and the proof it comes from us. */
export function forwardHeaders(request: Request) {
  const headers = new Headers();
  const client = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (client) headers.set("x-forwarded-for", client);
  const proof = proxyProof();
  if (proof) headers.set("x-nora-proxy", proof);
  return headers;
}

/**
 * A browser sending a state-changing request from another site is refused. Browsers always send
 * Origin on cross-site POSTs; calls without one (our own tests, scripts) cannot carry the cookies anyway.
 */
export function sameOriginOrNone(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return true;
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

// One refresh per refresh token at a time: parallel requests that all found the access token
// expired share the rotation that is under way. Once it has finished the entry is gone, so a used
// token presented later is refused by FastAPI (and treated as a replay).
const inflight = new Map<string, Promise<Tokens | null>>();

export function refreshTokens(request: Request, refreshToken: string): Promise<Tokens | null> {
  const running = inflight.get(refreshToken);
  if (running) return running;
  const task = (async () => {
    try {
      const response = await fetch(`${backendBaseUrl()}/auth/refresh`, {
        method: "POST",
        headers: { "content-type": "application/json", ...Object.fromEntries(forwardHeaders(request)) },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      });
      if (!response.ok) return null;
      const data = (await response.json()) as Tokens;
      return { access_token: data.access_token, refresh_token: data.refresh_token };
    } catch {
      return null;
    } finally {
      inflight.delete(refreshToken);
    }
  })();
  inflight.set(refreshToken, task);
  return task;
}
