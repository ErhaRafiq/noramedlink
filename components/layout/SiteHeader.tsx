"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LayoutDashboard, LogOut } from "lucide-react";

import { Button, ButtonLink } from "@/components/ui/button";
import { NoraLogo } from "@/components/ui/NoraLogo";
import { dashboardPathForRole, signOut as endSession } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { useStoredSession } from "@/hooks/use-stored-session";
import { useThrottledCallback } from "@/hooks/use-throttled-callback";

export type SiteLink = { href: string; label: string };

const DEFAULT_LINKS: SiteLink[] = [
  { href: "/doctors", label: "Find a doctor" },
  { href: "/summarize", label: "Summarize" },
  { href: "/about", label: "About" },
];

/**
 * Top bar for every page outside the dashboards. Shows sign in / get started when
 * signed out, and the user's dashboard and sign out when signed in. Gains a border and
 * shadow once the page scrolls (throttled listener).
 */
export function SiteHeader({ links = DEFAULT_LINKS }: { links?: SiteLink[] }) {
  const router = useRouter();
  const { ready, session } = useStoredSession();
  const [scrolled, setScrolled] = useState(false);
  const onScroll = useThrottledCallback(() => setScrolled(window.scrollY > 8), 100);

  useEffect(() => {
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, [onScroll]);

  function signOut() {
    void endSession();
    router.push("/");
  }

  return (
    <header
      className={cn(
        "sticky top-0 z-40 border-b transition-colors duration-200",
        scrolled ? "border-line bg-white/90 shadow-card backdrop-blur-xl" : "border-transparent bg-surface-page/70 backdrop-blur",
      )}
    >
      <nav aria-label="Main" className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <NoraLogo />
        <ul className="hidden items-center gap-8 text-sm font-medium text-slate-600 md:flex">
          {links.map((link) => (
            <li key={link.href}>
              <Link href={link.href} className="transition-colors hover:text-ink">
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
        {/* Reserve the space until the stored session is known, so the bar does not jump. */}
        <div className={cn("flex min-w-[150px] items-center justify-end gap-2", !ready && "invisible")}>
          {session ? (
            <>
              <ButtonLink href={dashboardPathForRole(session.user.role)} size="sm" icon={<LayoutDashboard className="h-4 w-4" />}>
                <span className="hidden sm:inline">My dashboard</span>
                <span className="sm:hidden">Dashboard</span>
              </ButtonLink>
              <Button variant="ghost" size="sm" onClick={signOut} icon={<LogOut className="h-4 w-4" />} aria-label="Sign out">
                <span className="hidden sm:inline">Sign out</span>
              </Button>
            </>
          ) : (
            <>
              <ButtonLink href="/login" variant="ghost" size="sm" className="hidden sm:inline-flex">
                Sign in
              </ButtonLink>
              <ButtonLink href="/signup?role=patient" size="sm">
                Get started
              </ButtonLink>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
