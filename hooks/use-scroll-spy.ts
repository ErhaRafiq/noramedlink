"use client";

import { useEffect, useState } from "react";

import { useThrottledCallback } from "@/hooks/use-throttled-callback";

/**
 * Which section the user is reading: the last of `ids` whose top has scrolled above
 * `offset` px from the top of the window, or `fallback` near the top of the page.
 * Scroll events are throttled, so the check runs at most every `throttleMs`.
 */
export function useScrollSpy(ids: readonly string[], { fallback, offset = 140, throttleMs = 100 }: { fallback: string; offset?: number; throttleMs?: number }) {
  const [active, setActive] = useState(fallback);

  const measure = useThrottledCallback(() => {
    let current = fallback;
    let currentTop = -Infinity;
    for (const id of ids) {
      const top = document.getElementById(id)?.getBoundingClientRect().top;
      if (top !== undefined && top - offset <= 0 && top > currentTop) {
        current = id;
        currentTop = top;
      }
    }
    setActive(current);
  }, throttleMs);

  useEffect(() => {
    window.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure, { passive: true });
    measure();
    return () => {
      window.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
    };
  }, [measure]);

  return [active, setActive] as const;
}
