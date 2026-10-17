"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useNotificationCenter } from "@/components/notifications/NotificationsProvider";
import { api } from "@/lib/api";
import type { AppNotification } from "@/lib/types";

type Options = {
  unreadOnly?: boolean;
  category?: string;
  pageSize?: number;
  /** A closed panel loads nothing. */
  enabled?: boolean;
};

/**
 * The signed-in user's notifications, newest first, filtered on the server, a page at a time. It refetches
 * when a filter changes or when the bell sees something new, and keeps the bell's count in step with what
 * it reads and changes.
 *
 * Marking read, marking all read and dismissing update the list at once, tell the server, then read the list
 * again so it shows the server's truth. An answer that was already on its way when the person made a change
 * is thrown away (the `epoch`), so a slow reply can never put an old list back over a newer one.
 */
export function useNotifications({ unreadOnly = false, category = "", pageSize = 20, enabled = true }: Options = {}) {
  const { version, setUnread } = useNotificationCenter();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [total, setTotal] = useState(0);
  const [unread, setUnreadHere] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const epoch = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    const started = epoch.current;
    let current = true;
    api
      .notifications({ limit: pageSize }, undefined, { unreadOnly, category })
      .then((page) => {
        if (!current || started !== epoch.current) return;
        setItems(page.items);
        setTotal(page.total);
        setUnreadHere(page.unread);
        setUnread(page.unread);
        setError("");
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (!current || started !== epoch.current) return;
        setError(err instanceof Error ? err.message : "Unable to load notifications.");
        setStatus("error");
      });
    return () => {
      current = false;
    };
  }, [attempt, category, enabled, pageSize, setUnread, unreadOnly, version]);

  const resync = useCallback(() => setAttempt((n) => n + 1), []);

  const loadMore = useCallback(async () => {
    const started = epoch.current;
    setLoadingMore(true);
    try {
      const page = await api.notifications({ limit: pageSize, offset: items.length }, undefined, { unreadOnly, category });
      if (started !== epoch.current) return;
      setItems((current) => [...current, ...page.items.filter((n) => !current.some((c) => c.id === n.id))]);
      setTotal(page.total);
      setUnreadHere(page.unread);
      setUnread(page.unread);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load more.");
    } finally {
      setLoadingMore(false);
    }
  }, [category, items.length, pageSize, setUnread, unreadOnly]);

  const markRead = useCallback(
    async (id: number) => {
      const was = items.find((n) => n.id === id);
      if (!was || was.read) return;
      epoch.current += 1;
      setItems((current) => current.map((n) => (n.id === id ? { ...n, read: true } : n)));
      const next = Math.max(0, unread - 1);
      setUnreadHere(next);
      setUnread(next);
      await api.markNotificationRead(id).catch(() => undefined);
      resync();
    },
    [items, resync, setUnread, unread],
  );

  const markAllRead = useCallback(async () => {
    epoch.current += 1;
    // In the unread view nothing is left to show; in the others the items stay, now read.
    setItems((current) => (unreadOnly ? [] : current.map((n) => ({ ...n, read: true }))));
    if (unreadOnly) setTotal(0);
    setUnreadHere(0);
    setUnread(0);
    await api.markAllNotificationsRead().catch(() => undefined);
    resync();
  }, [resync, setUnread, unreadOnly]);

  const dismiss = useCallback(
    async (id: number) => {
      const was = items.find((n) => n.id === id);
      epoch.current += 1;
      setItems((current) => current.filter((n) => n.id !== id));
      setTotal((count) => Math.max(0, count - 1));
      if (was && !was.read) {
        const next = Math.max(0, unread - 1);
        setUnreadHere(next);
        setUnread(next);
      }
      await api.dismissNotification(id).catch(() => undefined);
      resync();
    },
    [items, resync, setUnread, unread],
  );

  return {
    items,
    total,
    unread,
    status,
    error,
    loadingMore,
    hasMore: items.length < total,
    loadMore,
    markRead,
    markAllRead,
    dismiss,
    retry: () => {
      setStatus("loading");
      setAttempt((n) => n + 1);
    },
  };
}
