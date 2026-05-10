export const runtime = "nodejs";

type ReportsRouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

function backendBaseUrl() {
  return (
    process.env.SERVER_API_URL ||
    process.env.FASTAPI_URL ||
    DEFAULT_BACKEND_URL
  ).replace(/\/$/, "");
}

function forwardedHeaders(request: Request) {
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const authorization = request.headers.get("authorization");
  const accept = request.headers.get("accept");

  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (authorization) {
    headers.set("authorization", authorization);
  }
  if (accept) {
    headers.set("accept", accept);
  }

  return headers;
}

async function proxyToReportsBackend(request: Request, context: ReportsRouteContext) {
  const { path = [] } = await context.params;
  const incomingUrl = new URL(request.url);
  const suffix = path.map((segment) => encodeURIComponent(segment)).join("/");
  const backendPath = suffix ? `/patient/reports/${suffix}` : "/patient/reports";
  const targetUrl = `${backendBaseUrl()}${backendPath}${incomingUrl.search}`;
  const method = request.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";

  try {
    const backendResponse = await fetch(targetUrl, {
      method,
      headers: forwardedHeaders(request),
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
    });

    const responseHeaders = new Headers(backendResponse.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");

    return new Response(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown backend connection error.";
    return Response.json(
      {
        detail: `Patient report API is not reachable at ${backendBaseUrl()}. Start the FastAPI server and try again. (${message})`,
      },
      { status: 502 },
    );
  }
}

export function GET(request: Request, context: ReportsRouteContext) {
  return proxyToReportsBackend(request, context);
}

export function POST(request: Request, context: ReportsRouteContext) {
  return proxyToReportsBackend(request, context);
}

export function PATCH(request: Request, context: ReportsRouteContext) {
  return proxyToReportsBackend(request, context);
}

export function DELETE(request: Request, context: ReportsRouteContext) {
  return proxyToReportsBackend(request, context);
}

export function OPTIONS(request: Request, context: ReportsRouteContext) {
  return proxyToReportsBackend(request, context);
}
