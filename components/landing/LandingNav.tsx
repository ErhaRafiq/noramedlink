"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ButtonLink } from "@/components/ui/button";
import { NoraLogo } from "@/components/ui/NoraLogo";
import { cn } from "@/lib/cn";
import { useThrottledCallback } from "@/hooks/use-throttled-callback";

const LINKS = [
  { href: "/#features", label: "Features" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#safety", label: "Safety" },
  { href: "/about", label: "About" },
];

/** Top navigation for the public pages; gains a border and shadow once the page scrolls. */
export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  const onScroll = useThrottledCallback(() => setScrolled(window.scrollY > 8), 100);

  useEffect(() => {
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, [onScroll]);

  return (
    <header
      className={cn(
        "sticky top-0 z-40 border-b transition-colors duration-200",
        scrolled ? "border-line bg-white/90 shadow-card backdrop-blur-xl" : "border-transparent bg-surface-page/60 backdrop-blur",
      )}
    >
      <nav aria-label="Main" className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <NoraLogo />
        <ul className="hidden items-center gap-8 text-sm font-medium text-slate-600 md:flex">
          {LINKS.map((link) => (
            <li key={link.href}>
              <Link href={link.href} className="transition-colors hover:text-ink">
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-2">
          <ButtonLink href="/login" variant="ghost" size="sm" className="hidden sm:inline-flex">
            Sign in
          </ButtonLink>
          <ButtonLink href="/signup?role=patient" size="sm">
            Get started
          </ButtonLink>
        </div>
      </nav>
    </header>
  );
}
