"use client";

import { useCallback, useEffect, useRef } from "react";

/**
 * Wraps `callback` so it runs at most once every `waitMs`. The first call runs at once;
 * calls during the wait are collapsed into one trailing call with the latest arguments.
 * Use it for high-frequency events (scroll, resize, pointer move).
 */
export function useThrottledCallback<Args extends unknown[]>(callback: (...args: Args) => void, waitMs: number) {
  const callbackRef = useRef(callback);
  const lastRunRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const pendingArgsRef = useRef<Args | null>(null);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
  }, []);

  return useCallback(
    (...args: Args) => {
      const now = Date.now();
      const remaining = waitMs - (now - lastRunRef.current);
      if (remaining <= 0) {
        lastRunRef.current = now;
        callbackRef.current(...args);
        return;
      }
      pendingArgsRef.current = args;
      if (timerRef.current !== null) return;
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null;
        lastRunRef.current = Date.now();
        if (pendingArgsRef.current) callbackRef.current(...pendingArgsRef.current);
        pendingArgsRef.current = null;
      }, remaining);
    },
    [waitMs],
  );
}
