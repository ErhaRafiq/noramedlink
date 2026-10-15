"use client";

import { useMemo, useSyncExternalStore } from "react";

import { readSessionSnapshot, SESSION_CHANGE_EVENT, type StoredSession } from "@/lib/auth";
import type { AuthUser } from "@/lib/types";

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(SESSION_CHANGE_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(SESSION_CHANGE_EVENT, onChange);
  };
}

/**
 * The session saved in this browser, kept in sync across tabs, without a server check.
 * Use it for UI that only adapts to being signed in (headers, "sign in to continue");
 * protected pages use useAuthGuard, which confirms the session with the server.
 * `ready` is false during server rendering and the first client render.
 */
export function useStoredSession(): { ready: boolean; session: StoredSession | null } {
  const snapshot = useSyncExternalStore<string | null>(subscribe, readSessionSnapshot, () => null);

  return useMemo(() => {
    if (snapshot === null) return { ready: false, session: null };
    if (snapshot === "") return { ready: true, session: null };
    try {
      return { ready: true, session: { user: JSON.parse(snapshot) as AuthUser } };
    } catch {
      return { ready: true, session: null };
    }
  }, [snapshot]);
}
