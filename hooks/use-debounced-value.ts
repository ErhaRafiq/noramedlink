"use client";

import { useEffect, useState } from "react";

/**
 * Returns `value` once it has stopped changing for `delayMs`. Use it for search boxes
 * that trigger work (a request, an expensive filter) so it runs once per pause in
 * typing instead of on every keystroke.
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
