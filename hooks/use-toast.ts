"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type ToastType = "success" | "error" | "info";
export type ToastState = { type: ToastType; message: string } | null;

const DEFAULT_DURATION_MS = 3800;

/**
 * One toast at a time. A new toast replaces the current one and restarts the timer;
 * the timer is cleared on unmount, so no state update fires after the page is gone.
 */
export function useToast(durationMs = DEFAULT_DURATION_MS) {
  const [toast, setToast] = useState<ToastState>(null);
  const timerRef = useRef<number | null>(null);

  const dismiss = useCallback(() => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = null;
    setToast(null);
  }, []);

  const notify = useCallback(
    (type: ToastType, message: string) => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      setToast({ type, message });
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null;
        setToast(null);
      }, durationMs);
    },
    [durationMs],
  );

  useEffect(() => () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
  }, []);

  return { toast, notify, dismiss };
}

export type Notify = ReturnType<typeof useToast>["notify"];
