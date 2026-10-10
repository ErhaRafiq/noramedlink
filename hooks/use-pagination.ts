"use client";

import { useCallback, useMemo, useState } from "react";

/** Limit/offset paging state for lists the backend returns as { items, total, limit, offset }. */
export function usePagination({ pageSize = 20, initialPage = 1 }: { pageSize?: number; initialPage?: number } = {}) {
  const [page, setPage] = useState(initialPage);
  const [total, setTotal] = useState(0);

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const offset = (page - 1) * pageSize;

  const goTo = useCallback((next: number) => setPage(Math.max(1, Math.floor(next))), []);
  const next = useCallback(() => setPage((p) => p + 1), []);
  const previous = useCallback(() => setPage((p) => Math.max(1, p - 1)), []);
  const reset = useCallback(() => setPage(1), []);

  return useMemo(
    () => ({
      page,
      pageSize,
      offset,
      limit: pageSize,
      total,
      pageCount,
      hasNext: page < pageCount,
      hasPrevious: page > 1,
      setTotal,
      goTo,
      next,
      previous,
      reset,
    }),
    [page, pageSize, offset, total, pageCount, goTo, next, previous, reset],
  );
}
