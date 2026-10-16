"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { AuditLogRow } from "@/lib/types";

const PAGE = 15;

export type AuditFilters = { action: string; actor_role: string; subject: string };
export const NO_FILTERS: AuditFilters = { action: "", actor_role: "", subject: "" };

function toQuery(filters: AuditFilters) {
  const subject = Number(filters.subject);
  return {
    action: filters.action || undefined,
    actor_role: filters.actor_role || undefined,
    subject: Number.isInteger(subject) && subject > 0 ? subject : undefined,
  };
}

/** The audit log, filtered on the server, fifteen rows at a time. A new filter starts again at the top. */
export function useAuditLog(enabled: boolean, filters: AuditFilters) {
  const [rows, setRows] = useState<AuditLogRow[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [actions, setActions] = useState<Record<string, string>>({});
  const { action, actor_role, subject } = filters;

  useEffect(() => {
    if (!enabled) return;
    let live = true;
    api
      .adminAuditActions()
      .then((found) => live && setActions(found))
      .catch(() => undefined); // the filter then shows no actions; the log itself still loads
    return () => {
      live = false;
    };
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    // A short pause so typing a patient number does not send a request per digit.
    const timer = window.setTimeout(() => {
      setFetching(true);
      api
        .adminAuditLog(toQuery({ action, actor_role, subject }), { limit: PAGE, offset: 0 })
        .then((page) => {
          if (controller.signal.aborted) return;
          setRows(page.items);
          setTotal(page.total);
          setError("");
          setStatus("ready");
          setFetching(false);
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setError(err instanceof Error ? err.message : "The audit log could not be loaded.");
          setStatus("error");
          setFetching(false);
        });
    }, 250);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [enabled, action, actor_role, subject, attempt]);

  const retry = useCallback(() => {
    setStatus("loading");
    setAttempt((n) => n + 1);
  }, []);

  const loadMore = useCallback(async () => {
    if (loadingMore || rows.length >= total) return;
    setLoadingMore(true);
    try {
      const page = await api.adminAuditLog(toQuery({ action, actor_role, subject }), { limit: PAGE, offset: rows.length });
      setRows((current) => [...current, ...page.items.filter((row) => !current.some((c) => c.id === row.id))]);
      setTotal(page.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "More could not be loaded.");
    } finally {
      setLoadingMore(false);
    }
  }, [action, actor_role, loadingMore, rows.length, subject, total]);

  return { rows, total, status, error, loadingMore, fetching, actions, retry, loadMore };
}
