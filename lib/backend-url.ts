const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

/** FastAPI base URL. Server-side configuration only; never taken from the request. */
export function backendBaseUrl() {
  return (
    process.env.SERVER_API_URL ||
    process.env.FASTAPI_URL ||
    DEFAULT_BACKEND_URL
  ).replace(/\/$/, "");
}

/**
 * Builds the FastAPI URL for proxied path segments, or returns null if the path could
 * leave the configured backend: no segments, empty, "." or ".." segments, or control
 * characters. Each segment is percent-encoded, so "/", "\", "@" and ":" cannot change
 * the host, and the final URL must keep the backend's origin and path prefix.
 */
export function buildBackendUrl(segments: string[], search: string, baseUrl = backendBaseUrl()) {
  if (segments.length === 0) {
    return null;
  }

  for (const segment of segments) {
    if (segment === "" || segment === "." || segment === ".." || /[\u0000-\u001f\u007f]/.test(segment)) {
      return null;
    }
  }

  const base = new URL(`${baseUrl}/`);
  const target = new URL(segments.map((segment) => encodeURIComponent(segment)).join("/"), base);

  if (target.origin !== base.origin || !target.pathname.startsWith(base.pathname)) {
    return null;
  }

  target.search = search;
  return target.toString();
}
