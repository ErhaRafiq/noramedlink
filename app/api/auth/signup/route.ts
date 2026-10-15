import { startSession } from "@/lib/auth-routes";

export const runtime = "nodejs";

export function POST(request: Request) {
  return startSession(request, "signup");
}
