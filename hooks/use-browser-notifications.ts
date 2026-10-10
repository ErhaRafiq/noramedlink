"use client";

import { useCallback, useEffect, useState } from "react";

export type NotificationPermissionState = NotificationPermission | "unsupported";

function readPermission(): NotificationPermissionState {
  if (typeof window === "undefined" || !("Notification" in window)) return "unsupported";
  return Notification.permission;
}

/** Browser notification permission, read after mount, plus a function to ask for it. */
export function useNotificationPermission() {
  const [permission, setPermission] = useState<NotificationPermissionState>("unsupported");

  useEffect(() => {
    // Read after mount so the server render and the first client render match.
    const timer = window.setTimeout(() => setPermission(readPermission()), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const request = useCallback(async () => {
    if (readPermission() !== "default") return;
    setPermission(await Notification.requestPermission());
  }, []);

  return { permission, request };
}

export type ScheduledNotification = { id: string | number; at: string; title: string; body: string };

/**
 * Shows a browser notification at each item's time while the page is open. Only items
 * due within `windowMs` are scheduled; timers are replaced whenever the list changes.
 */
export function useScheduledNotifications(
  items: ScheduledNotification[],
  enabled: boolean,
  windowMs = 24 * 60 * 60 * 1000,
) {
  useEffect(() => {
    if (!enabled) return;
    const timers = items
      .map((item) => {
        const delay = new Date(item.at).getTime() - Date.now();
        if (delay <= 0 || delay > windowMs) return null;
        return window.setTimeout(() => {
          new Notification(item.title, { body: item.body, tag: String(item.id) });
        }, delay);
      })
      .filter((timer): timer is number => timer !== null);
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [items, enabled, windowMs]);
}
