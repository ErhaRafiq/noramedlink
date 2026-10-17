"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { AdminDoctorRow } from "@/lib/types";

const PAGE = 10;

export type DoctorFilters = { approval: string; pmdc: string; q: string };
export const NO_DOCTOR_FILTERS: DoctorFilters = { approval: "", pmdc: "", q: "" };

/** Every doctor with approval and PMDC status, filtered on the server, ten at a time. */
export function useAdminDoctors(enabled: boolean, filters: DoctorFilters, refreshKey = 0) {
  const [rows, setRows] = useState<AdminDoctorRow[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const { approval, pmdc, q } = filters;

  useEffect(() => {
    if (!enabled) return;
    let live = true;
    // A short pause so typing a name does not send a request per letter.
    const timer = window.setTimeout(() => {
      setFetching(true);
      api
        .adminDoctors({ approval, pmdc, q: q.trim() }, { limit: PAGE, offset: 0 })
        .then((page) => {
          if (!live) return;
          setRows(page.items);
          setTotal(page.total);
          setError("");
          setStatus("ready");
          setFetching(false);
        })
        .catch((err: unknown) => {
          if (!live) return;
          setError(err instanceof Error ? err.message : "The doctor list could not be loaded.");
          setStatus("error");
          setFetching(false);
        });
    }, 250);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [enabled, approval, pmdc, q, attempt, refreshKey]);

  const retry = useCallback(() => {
    setStatus("loading");
    setAttempt((n) => n + 1);
  }, []);

  const loadMore = useCallback(async () => {
    if (loadingMore || rows.length >= total) return;
    setLoadingMore(true);
    try {
      const page = await api.adminDoctors({ approval, pmdc, q: q.trim() }, { limit: PAGE, offset: rows.length });
      setRows((current) => [...current, ...page.items.filter((row) => !current.some((c) => c.id === row.id))]);
      setTotal(page.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "More could not be loaded.");
    } finally {
      setLoadingMore(false);
    }
  }, [approval, loadingMore, pmdc, q, rows.length, total]);

  return { rows, total, status, error, loadingMore, fetching, retry, loadMore };
}
