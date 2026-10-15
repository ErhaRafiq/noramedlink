"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { MedicalDocument } from "@/lib/types";

type Result = { key: string; items: MedicalDocument[]; total: number; error: string | null };

const EMPTY: Result = { key: "", items: [], total: 0, error: null };

/**
 * The patient's reports, searched and filtered on the server, one page at a time.
 * A new search or department starts again at page one; the previous request is
 * cancelled so a slow response can never overwrite a newer one. Pass an already
 * debounced `search` so typing does not send a request per keystroke.
 */
export function useReportList({
  signedIn,
  search,
  department,
  pageSize = 10,
}: {
  signedIn: boolean;
  search: string;
  department: string | null;
  pageSize?: number;
}) {
  const [version, setVersion] = useState(0);
  const [result, setResult] = useState<Result>(EMPTY);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const key = `${search.trim()}|${department ?? ""}|${version}`;

  useEffect(() => {
    if (!signedIn) return;
    const controller = new AbortController();
    api
      .reports({ limit: pageSize, offset: 0, q: search, department: department ?? undefined }, { signal: controller.signal })
      .then((page) => setResult({ key, items: page.items, total: page.total, error: null }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setResult({ key, items: [], total: 0, error: error instanceof Error ? error.message : "Unable to load reports." });
      });
    return () => controller.abort();
  }, [department, key, pageSize, search, signedIn]);

  const loadMore = useCallback(async () => {
    if (!signedIn || isLoadingMore || result.key !== key || result.items.length >= result.total) return;
    setIsLoadingMore(true);
    try {
      const page = await api.reports({
        limit: pageSize,
        offset: result.items.length,
        q: search,
        department: department ?? undefined,
      });
      setResult((current) =>
        current.key === key
          ? { ...current, items: [...current.items, ...page.items.filter((r) => !current.items.some((c) => c.id === r.id))], total: page.total }
          : current,
      );
    } catch (error) {
      setResult((current) => (current.key === key ? { ...current, error: error instanceof Error ? error.message : "Unable to load more reports." } : current));
    } finally {
      setIsLoadingMore(false);
    }
  }, [department, isLoadingMore, key, pageSize, result, search, signedIn]);

  /** Reloads page one, e.g. after an upload. */
  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  const isLoading = result.key !== key;
  return {
    // While a new page one loads, keep showing the previous results instead of flashing empty.
    items: result.items,
    total: result.total,
    error: isLoading ? null : result.error,
    isLoading,
    isLoadingMore,
    hasMore: !isLoading && result.items.length < result.total,
    loadMore,
    refresh,
  };
}
