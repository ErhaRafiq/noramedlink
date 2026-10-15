import { backendBaseUrl, buildBackendUrl } from "@/lib/backend-url";
import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  clearedCookies,
  forwardHeaders,
  readCookies,
  refreshTokens,
  sameOriginOrNone,
  sessionCookies,
  withCookies,
} from "@/lib/server-session";

export const runtime = "nodejs";

type BackendRouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

// Sign-in, sign-up, refresh and logout hand out or end tokens, so they are only reachable through
// app/api/auth, which keeps the tokens in HttpOnly cookies. They are not forwarded from here.
const TOKEN_ROUTES = /^(?:api\/)?auth\/(?:login|signup|refresh|logout)$/;
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

async function send(targetUrl: string, request: Request, body: ArrayBuffer | undefined, accessToken: string | null) {
  const headers = forwardHeaders(request);
  for (const name of ["content-type", "accept"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  // A script or test may send its own Authorization header; a browser's identity is its cookie.
  const supplied = request.headers.get("authorization");
  if (supplied) headers.set("authorization", supplied);
  else if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);
  return fetch(targetUrl, { method: request.method.toUpperCase(), headers, body, cache: "no-store" });
}

async function proxyToBackend(request: Request, context: BackendRouteContext) {
  const { path } = await context.params;
  if (TOKEN_ROUTES.test((path ?? []).join("/"))) {
    return Response.json({ detail: "Not found." }, { status: 404 });
  }
  const method = request.method.toUpperCase();
  if (!SAFE_METHODS.has(method) && !sameOriginOrNone(request)) {
    return Response.json({ detail: "Cross-site request refused." }, { status: 403 });
  }
  const incomingUrl = new URL(request.url);
  const targetUrl = buildBackendUrl(path ?? [], incomingUrl.search);

  if (!targetUrl) {
    return Response.json({ detail: "Invalid backend path." }, { status: 400 });
  }

  const cookies = readCookies(request);
  const body = method !== "GET" && method !== "HEAD" ? await request.arrayBuffer() : undefined;
  let accessToken = cookies[ACCESS_COOKIE] ?? null;
  let newCookies: string[] | null = null;
  const ownIdentity = !request.headers.get("authorization");

  try {
    let backendResponse: Response | null = null;
    if (accessToken || !ownIdentity || !cookies[REFRESH_COOKIE]) {
      backendResponse = await send(targetUrl, request, body, accessToken);
    }
    if ((backendResponse === null || backendResponse.status === 401) && ownIdentity && cookies[REFRESH_COOKIE]) {
      // The short-lived access token expired (or is missing): rotate the session once and retry.
      const renewed = await refreshTokens(request, cookies[REFRESH_COOKIE]);
      if (renewed) {
        accessToken = renewed.access_token;
        newCookies = sessionCookies(renewed);
        backendResponse = await send(targetUrl, request, body, accessToken);
      } else {
        newCookies = clearedCookies();
        backendResponse ??= await send(targetUrl, request, body, null);
      }
    }
    if (backendResponse === null) backendResponse = await send(targetUrl, request, body, accessToken);

    const responseHeaders = new Headers(backendResponse.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");

    const response = new Response(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
    return newCookies ? withCookies(response, newCookies) : response;
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown backend connection error.";

    return Response.json(
      {
        detail: `Backend API is not reachable at ${backendBaseUrl()}. Start the FastAPI server and try again. (${message})`,
      },
      { status: 502 },
    );
  }
}

export function GET(request: Request, context: BackendRouteContext) {
  return proxyToBackend(request, context);
}

export function POST(request: Request, context: BackendRouteContext) {
  return proxyToBackend(request, context);
}

export function PUT(request: Request, context: BackendRouteContext) {
  return proxyToBackend(request, context);
}

export function PATCH(request: Request, context: BackendRouteContext) {
  return proxyToBackend(request, context);
}

export function DELETE(request: Request, context: BackendRouteContext) {
  return proxyToBackend(request, context);
}

export function HEAD(request: Request, context: BackendRouteContext) {
  return proxyToBackend(request, context);
}

export function OPTIONS(request: Request, context: BackendRouteContext) {
  return proxyToBackend(request, context);
}
