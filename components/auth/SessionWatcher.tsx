"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { clearSession, getSession, isProtectedPath, loginUrl, verifySession } from "@/lib/auth";

const RECHECK_MS = 60_000; // returning to a tab asks the server again, at most once a minute
const PROFILE_KEY = "nora_medlink_user";

/**
 * Keeps the stored profile honest, on every page (mounted once in the root layout; renders nothing):
 * - a profile whose cookie session is gone (expired, signed out elsewhere, password changed) is cleared, so
 *   no page keeps looking signed in; on a signed-in page the person goes to /login and comes back after;
 * - signing out in another tab signs this tab out too.
 * Sign out in this tab navigates by itself, so the same-tab change is not acted on here.
 */
export function SessionWatcher() {
  const router = useRouter();
  const pathname = usePathname();
  const lastCheck = useRef(0);
  const path = useRef(pathname);

  useEffect(() => {
    path.current = pathname;
  }, [pathname]);

  useEffect(() => {
    const controller = new AbortController();

    async function check() {
      if (!getSession()) return;
      lastCheck.current = Date.now();
      if ((await verifySession(controller.signal)) !== "lost" || controller.signal.aborted) return;
      clearSession();
      if (isProtectedPath(path.current)) router.replace(loginUrl(path.current, "expired"));
    }

    function onVisible() {
      if (document.visibilityState === "visible" && Date.now() - lastCheck.current > RECHECK_MS) void check();
    }

    function onStorage(event: StorageEvent) {
      if (event.key !== PROFILE_KEY && event.key !== null) return;
      if (!getSession() && isProtectedPath(path.current)) router.replace("/login");
    }

    void check();
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    window.addEventListener("storage", onStorage);
    return () => {
      controller.abort();
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
      window.removeEventListener("storage", onStorage);
    };
  }, [router]);

  return null;
}
