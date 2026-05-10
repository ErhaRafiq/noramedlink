import { proxyAuthPost } from "@/lib/backend-auth-proxy";

export const runtime = "nodejs";

export function POST(request: Request) {
  return proxyAuthPost(request, "signup");
}
