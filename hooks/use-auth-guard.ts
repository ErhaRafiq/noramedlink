"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, isApiError } from "@/lib/api";
import { clearSession, dashboardPathForRole, getSession, updateStoredUser } from "@/lib/auth";
import type { AuthUser } from "@/lib/types";

type Role = AuthUser["role"];

export type AuthGuardState =
  | { status: "checking" }
  | { status: "ready"; user: AuthUser }
  | { status: "error"; message: string };

/**
 * Protects a page for one role. Reads the stored profile after mount (so server and
 * client renders match), confirms the cookie session with /auth/me, and:
 * - no profile, or the server rejects the session (401/403): clears it and goes to /login;
 * - signed in with another role: goes to that role's dashboard;
 * - backend unreachable: reports an error but keeps the session, so a retry can work.
 */
export function useAuthGuard(role: Role): AuthGuardState {
  const router = useRouter();
  const [state, setState] = useState<AuthGuardState>({ status: "checking" });

  useEffect(() => {
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }

    const controller = new AbortController();
    api
      .me({ signal: controller.signal })
      .then((user) => {
        if (user.role !== role) {
          router.replace(dashboardPathForRole(user.role));
          return;
        }
        updateStoredUser(user);
        setState({ status: "ready", user });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (isApiError(error, 401) || isApiError(error, 403)) {
          clearSession();
          router.replace("/login");
          return;
        }
        setState({ status: "error", message: error instanceof Error ? error.message : "Unable to check your session." });
      });

    return () => controller.abort();
  }, [role, router]);

  return state;
}
