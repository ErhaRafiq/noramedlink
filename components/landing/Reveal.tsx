"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * Fades content up the first time it scrolls into view.
 *
 * The server renders content visible, so the page reads fine before JavaScript runs,
 * with JavaScript off, and for crawlers. After mount, only elements that start below
 * the fold are hidden and then revealed by an IntersectionObserver; anything already
 * on screen is left alone, so nothing flashes. Reduced motion skips the effect.
 */
export function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element || !("IntersectionObserver" in window)) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (element.getBoundingClientRect().top < window.innerHeight) return; // already visible

    element.dataset.reveal = "hidden";
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        element.style.transitionDelay = `${delay}s`;
        element.dataset.reveal = "shown";
        observer.disconnect();
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [delay]);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
