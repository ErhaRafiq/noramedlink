import { backendBaseUrl } from "@/lib/backend-url";
import { REFRESH_COOKIE, clearedCookies, forwardHeaders, readCookies, sameOriginOrNone, sessionCookies, withCookies, type Tokens } from "@/lib/server-session";
import type { AuthUser } from "@/lib/types";

const unreachable = (error: unknown) =>
  Response.json(
    { detail: `Backend API is not reachable at ${backendBaseUrl()}. Start the FastAPI server and try again. (${error instanceof Error ? error.message : "unknown error"})` },
    { status: 502 },
  );

/** Login or signup: FastAPI's tokens go into HttpOnly cookies; the browser gets only the user. */
export async function startSession(request: Request, path: "login" | "signup") {
  if (!sameOriginOrNone(request)) return Response.json({ detail: "Cross-site request refused." }, { status: 403 });
  try {
    const backend = await fetch(`${backendBaseUrl()}/auth/${path}`, {
      method: "POST",
      headers: { "content-type": request.headers.get("content-type") ?? "application/json", ...Object.fromEntries(forwardHeaders(request)) },
      body: await request.text(),
      cache: "no-store",
    });
    if (!backend.ok) {
      const headers = new Headers({ "content-type": backend.headers.get("content-type") ?? "application/json" });
      const retryAfter = backend.headers.get("retry-after");
      if (retryAfter) headers.set("retry-after", retryAfter);
      return new Response(backend.body, { status: backend.status, headers });
    }
    const data = (await backend.json()) as Tokens & { user: AuthUser };
    return withCookies(Response.json({ user: data.user }, { status: backend.status }), sessionCookies(data));
  } catch (error) {
    return unreachable(error);
  }
}

/** Logout: ends the session on the server (its whole refresh-token family) and clears the cookies. */
export async function endSession(request: Request) {
  if (!sameOriginOrNone(request)) return Response.json({ detail: "Cross-site request refused." }, { status: 403 });
  const refreshToken = readCookies(request)[REFRESH_COOKIE];
  if (refreshToken) {
    try {
      await fetch(`${backendBaseUrl()}/auth/logout`, {
        method: "POST",
        headers: { "content-type": "application/json", ...Object.fromEntries(forwardHeaders(request)) },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      });
    } catch {
      // The cookies are cleared either way; an unreachable backend leaves the token to expire.
    }
  }
  return withCookies(Response.json({ message: "Signed out." }), clearedCookies());
}
