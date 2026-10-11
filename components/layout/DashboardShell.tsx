"use client";

import type { ReactNode } from "react";
import { LogOut, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { NoraLogo } from "@/components/ui/NoraLogo";
import { cn } from "@/lib/cn";
import { useScrollSpy } from "@/hooks/use-scroll-spy";

export type DashboardNavItem = { id: string; label: string; icon: LucideIcon };

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  window.history.replaceState(null, "", `#${id}`);
}

/**
 * Frame for the doctor and admin dashboards. Large screens: a navy sidebar with the
 * section links and the account. Phones: a compact top bar with sign out and a scrolling
 * row of section links. The active link follows the section being read.
 */
export function DashboardShell({
  nav,
  userName,
  userMeta,
  onSignOut,
  children,
}: {
  nav: DashboardNavItem[];
  userName: string;
  userMeta?: string;
  onSignOut: () => void;
  children: ReactNode;
}) {
  const [first, ...rest] = nav;
  const [active, setActive] = useScrollSpy(
    rest.map((item) => item.id),
    { fallback: first?.id ?? "" },
  );

  function go(id: string) {
    setActive(id);
    scrollTo(id);
  }

  return (
    <div className="min-h-screen bg-surface-page">
      <aside className="nm-sidebar fixed inset-y-3 left-3 z-30 hidden w-[248px] flex-col lg:flex">
        <NoraLogo inverse />
        <nav aria-label="Dashboard sections" className="mt-8 flex-1 space-y-1 overflow-y-auto">
          {nav.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => go(item.id)}
              aria-current={active === item.id ? "true" : undefined}
              className={cn("nm-sidebar-item w-full text-left", active === item.id && "nm-sidebar-item-active")}
            >
              <item.icon className="h-4 w-4" aria-hidden />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="border-t border-white/10 pt-4">
          <p className="truncate text-sm font-semibold text-white">{userName}</p>
          {userMeta ? <p className="truncate text-xs text-slate-300">{userMeta}</p> : null}
          <button type="button" onClick={onSignOut} className="nm-sidebar-item mt-3 w-full text-left text-slate-300">
            <LogOut className="h-4 w-4" aria-hidden />
            Sign out
          </button>
        </div>
      </aside>

      <header className="sticky top-0 z-20 border-b border-line bg-white/90 backdrop-blur-xl lg:hidden">
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <NoraLogo />
          <Button variant="ghost" size="sm" onClick={onSignOut} icon={<LogOut className="h-4 w-4" />}>
            Sign out
          </Button>
        </div>
        <nav aria-label="Dashboard sections" className="flex gap-2 overflow-x-auto px-4 pb-3">
          {nav.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => go(item.id)}
              aria-current={active === item.id ? "true" : undefined}
              className={cn(
                "inline-flex flex-shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                active === item.id ? "border-brand-blue bg-blue-50 text-brand-blue" : "border-line bg-white text-slate-600 hover:text-ink",
              )}
            >
              <item.icon className="h-3.5 w-3.5" aria-hidden />
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="min-w-0 lg:pl-[272px]">
        <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:py-8">{children}</div>
      </main>
    </div>
  );
}
