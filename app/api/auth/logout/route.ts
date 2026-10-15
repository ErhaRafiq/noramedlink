import { endSession } from "@/lib/auth-routes";

export const runtime = "nodejs";

export function POST(request: Request) {
  return endSession(request);
}
