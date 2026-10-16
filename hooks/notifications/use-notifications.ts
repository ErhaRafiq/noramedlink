"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { AppNotification } from "@/lib/types";

const PAGE_SIZE = 20;

/** The signed-in user's notifications (newest first), with mark-read actions. */
export function useNotifications() {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [total, setTotal] = useState(0);
  const [unread, setUnread] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    api
      .notifications({ limit: PAGE_SIZE })
      .then((page) => {
        if (!current) return;
        setItems(page.items);
        setTotal(page.total);
        setUnread(page.unread);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (!current) return;
        setError(err instanceof Error ? err.message : "Unable to load notifications.");
        setStatus("error");
      });
    return () => {
      current = false;
    };
  }, [attempt]);

  const loadMore = useCallback(async () => {
    setLoadingMore(true);
    try {
      const page = await api.notifications({ limit: PAGE_SIZE, offset: items.length });
      setItems((current) => [...current, ...page.items]);
      setTotal(page.total);
      setUnread(page.unread);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load more.");
    } finally {
      setLoadingMore(false);
    }
  }, [items.length]);

  const markRead = useCallback(async (id: number) => {
    setItems((current) => current.map((n) => (n.id === id ? { ...n, read: true } : n)));
    setUnread((n) => Math.max(0, n - 1));
    await api.markNotificationRead(id).catch(() => undefined);
  }, []);

  const markAllRead = useCallback(async () => {
    setItems((current) => current.map((n) => ({ ...n, read: true })));
    setUnread(0);
    await api.markAllNotificationsRead().catch(() => undefined);
  }, []);

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
    retry: () => {
      setStatus("loading");
      setAttempt((n) => n + 1);
    },
  };
}
