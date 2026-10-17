"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { ApiError, api } from "@/lib/api";
import { NOTIFICATIONS_CHANGED_EVENT } from "@/lib/notifications";
import type { AppNotification } from "@/lib/types";
import { useStoredSession } from "@/hooks/use-stored-session";
import { NotificationToaster } from "./NotificationToaster";

const POLL_MS = 30_000;
const MAX_BACKOFF_MS = 5 * 60_000;
const MAX_TOASTS = 3;

type Center = {
  /** Notifications the person has not read. */
  unread: number;
  /** Goes up whenever something new arrived: open lists refetch when it changes. */
  version: number;
  /** A list that has just read the server's count keeps the bell in step with it. */
  setUnread: (count: number) => void;
};

const CenterContext = createContext<Center>({ unread: 0, version: 0, setUnread: () => undefined });

export const useNotificationCenter = () => useContext(CenterContext);

/**
 * The one place that watches for new notifications, for every page: a cheap count every 30 seconds while the
 * tab is visible, and straight away when the tab is shown again, the window gets focus, the connection comes
 * back, or code that has just caused a notification asks (requestNotificationRefresh). After a failure it waits
 * longer, up to five minutes, and one 401 (signed out) stops it until the person signs in again. A rise in the
 * count fetches the newest unread items and shows them as toasts; the first check only sets the baseline, so a
 * page load never toasts old notifications.
 */
export function NotificationsProvider({ children }: { children: ReactNode }) {
  const { ready, session } = useStoredSession();
  const userId = session?.user.id ?? null;
  const signedIn = ready && userId !== null;
  const [unread, setUnread] = useState(0);
  const [version, setVersion] = useState(0);
  const [toasts, setToasts] = useState<AppNotification[]>([]);
  const baseline = useRef<number | null>(null);
  const failures = useRef(0);

  useEffect(() => {
    if (!signedIn) return;
    baseline.current = null;
    failures.current = 0;
    let stopped = false;
    let timer = 0;

    const check = async (): Promise<boolean> => {
      try {
        const { unread: count } = await api.unreadNotificationCount();
        if (stopped) return true;
        const before = baseline.current;
        baseline.current = count;
        setUnread(count);
        if (before === null || count !== before) setVersion((v) => v + 1);
        if (before !== null && count > before) {
          const page = await api.notifications({ limit: Math.min(count - before, MAX_TOASTS) }, undefined, { unreadOnly: true });
          if (!stopped) setToasts((current) => [...page.items, ...current].slice(0, MAX_TOASTS));
        }
        failures.current = 0;
        return true;
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          stopped = true; // signed out: nothing to watch until the next sign-in
          return true;
        }
        failures.current += 1;
        return false;
      }
    };

    const schedule = (ms: number) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(run, ms);
    };
    const run = async () => {
      if (stopped) return;
      if (document.visibilityState === "hidden") return schedule(POLL_MS); // a hidden tab asks nothing
      const ok = await check();
      schedule(ok ? POLL_MS : Math.min(POLL_MS * 2 ** failures.current, MAX_BACKOFF_MS));
    };
    const nudge = () => {
      if (document.visibilityState !== "hidden") void run();
    };

    document.addEventListener("visibilitychange", nudge);
    window.addEventListener("focus", nudge);
    window.addEventListener("online", nudge);
    window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, nudge);
    void run();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", nudge);
      window.removeEventListener("focus", nudge);
      window.removeEventListener("online", nudge);
      window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, nudge);
    };
  }, [signedIn, userId]);

  const keepInStep = useCallback((count: number) => {
    baseline.current = count; // a count the person already saw must not toast
    setUnread(count);
  }, []);

  const value = useMemo<Center>(
    () => ({ unread: signedIn ? unread : 0, version, setUnread: keepInStep }),
    [keepInStep, signedIn, unread, version],
  );

  return (
    <CenterContext.Provider value={value}>
      {children}
      {signedIn ? <NotificationToaster toasts={toasts} onDismiss={(id) => setToasts((current) => current.filter((t) => t.id !== id))} /> : null}
    </CenterContext.Provider>
  );
}
