import { NextResponse, type NextRequest } from "next/server";

const ACCESS_COOKIE = "nora_at";
const REFRESH_COOKIE = "nora_rt";

/**
 * First gate for the signed-in areas: a request with no session cookie at all goes to /login (and comes back
 * to the page after signing in) before any page code runs. Whether the session is still valid is checked by
 * the page itself (useAuthGuard) and by the API, which renew or refuse it; this only turns away visitors who
 * have no session to check. Keep the matcher in step with PROTECTED_PREFIXES in lib/auth.ts.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(ACCESS_COOKIE) || request.cookies.has(REFRESH_COOKIE)) return NextResponse.next();
  const { pathname, search } = request.nextUrl;
  const login = new URL("/login", request.url);
  login.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/admin/:path*",
    "/profile/:path*",
    "/notifications/:path*",
    "/payments/:path*",
  ],
};
