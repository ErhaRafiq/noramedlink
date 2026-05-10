const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

function backendBaseUrl() {
  return (
    process.env.SERVER_API_URL ||
    process.env.FASTAPI_URL ||
    DEFAULT_BACKEND_URL
  ).replace(/\/$/, "");
}

export async function proxyAuthPost(request: Request, authPath: string) {
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");

  if (contentType) {
    headers.set("content-type", contentType);
  }

  if (accept) {
    headers.set("accept", accept);
  }

  try {
    const requestBody = await request.text();
    const requestInit = {
      method: "POST",
      headers,
      body: requestBody,
      cache: "no-store" as const,
    };

    let backendResponse = await fetch(`${backendBaseUrl()}/auth/${authPath}`, requestInit);
    if (backendResponse.status === 404) {
      backendResponse = await fetch(`${backendBaseUrl()}/api/auth/${authPath}`, requestInit);
    }

    const responseHeaders = new Headers(backendResponse.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");

    return new Response(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
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
