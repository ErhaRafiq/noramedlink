"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { AccessHistoryRow } from "@/lib/types";

const PAGE = 10;

/** Who else viewed or changed the signed-in patient's record, newest first, ten at a time. */
export function useAccessHistory(enabled = true) {
  const [items, setItems] = useState<AccessHistoryRow[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let live = true;
    api
      .accessHistory({ limit: PAGE, offset: 0 })
      .then((page) => {
        if (!live) return;
        setItems(page.items);
        setTotal(page.total);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (!live) return;
        setError(err instanceof Error ? err.message : "The access history could not be loaded.");
        setStatus("error");
      });
    return () => {
      live = false;
    };
  }, [enabled, attempt]);

  const retry = useCallback(() => {
    setStatus("loading");
    setError("");
    setAttempt((n) => n + 1);
  }, []);

  const loadMore = useCallback(async () => {
    if (loadingMore || items.length >= total) return;
    setLoadingMore(true);
    try {
      const page = await api.accessHistory({ limit: PAGE, offset: items.length });
      setItems((current) => [...current, ...page.items.filter((row) => !current.some((c) => c.id === row.id))]);
      setTotal(page.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "More could not be loaded.");
    } finally {
      setLoadingMore(false);
    }
  }, [items.length, loadingMore, total]);

  return { items, total, status, error, loadingMore, retry, loadMore };
}
