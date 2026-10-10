"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import { usePrefersReducedMotion } from "@/hooks/use-media-query";
import { HeroFallbackArt } from "./HeroFallbackArt";

// Three.js is loaded only on the client, in its own chunk, after the page has rendered.
const HeroScene = dynamic(() => import("./HeroScene"), {
  ssr: false,
  loading: () => <HeroFallbackArt />,
});

/**
 * Hero artwork: the 3D scene, animated only while it is on screen and only when the
 * user has not asked the OS to reduce motion (then it renders one still frame).
 */
export function HeroVisual() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(true);
  const reduceMotion = usePrefersReducedMotion();

  useEffect(() => {
    const element = containerRef.current;
    if (!element || !("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 0.05 });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="relative aspect-square w-full max-w-[400px] lg:max-w-[560px]">
      <div aria-hidden className="absolute inset-[12%] rounded-full bg-gradient-to-br from-brand-blue/10 to-brand-teal/10 blur-3xl" />
      <div className="relative h-full w-full">
        <HeroScene animate={inView && !reduceMotion} />
      </div>
    </div>
  );
}
