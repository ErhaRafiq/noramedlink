"use client";

import {
  Activity,
  Bell,
  CalendarDays,
  FileText,
  HeartPulse,
  Home,
  KeyRound,
  LockKeyhole,
  LogOut,
  UserRound,
  Pill,
  Plus,
  Search,
  Settings,
  Siren,
  Sparkles,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";

import { NotificationLink } from "@/components/notifications/NotificationLink";
import { Button, ButtonLink } from "@/components/ui/button";
import { NoraLogo } from "@/components/ui/NoraLogo";
import { cn } from "@/lib/cn";

export const NAV_ITEMS: Array<{ id: string; label: string; icon: LucideIcon }> = [
  { id: "dashboard", label: "Overview", icon: Home },
  { id: "care-team", label: "Doctor access", icon: KeyRound },
  { id: "vitals", label: "Vitals", icon: Activity },
  { id: "medications", label: "Today's medicines", icon: Pill },
  { id: "reports", label: "My reports", icon: FileText },
  { id: "insights", label: "Health flags", icon: HeartPulse },
  { id: "appointments", label: "Appointments", icon: CalendarDays },
  { id: "reminders", label: "Reminders", icon: Bell },
  { id: "settings", label: "Account", icon: Settings },
];

const QUICK_LINKS: Array<{ href: string; label: string; icon: LucideIcon }> = [
  { href: "/doctors", label: "Find a doctor", icon: Stethoscope },
  { href: "/summarize", label: "Summarize a report", icon: Sparkles },
  { href: "/emergency", label: "Home visit", icon: Siren },
];

export function WorkspaceSidebar({
  activeNav,
  onNavigate,
  userName,
}: {
  activeNav: string;
  onNavigate: (id: string) => void;
  userName: string | null;
}) {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[264px] flex-col border-r border-line bg-white xl:flex">
      <div className="border-b border-line px-5 py-4">
        <NoraLogo />
      </div>

      <nav aria-label="Dashboard sections" className="flex-1 space-y-1 overflow-y-auto p-3">
        {NAV_ITEMS.map((item) => {
          const isActive = activeNav === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              aria-current={isActive ? "true" : undefined}
              className={cn(
                "flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-left text-sm font-medium transition-colors",
                isActive ? "bg-blue-50 text-brand-blue" : "text-slate-600 hover:bg-surface-soft hover:text-ink",
              )}
            >
              <item.icon className={cn("h-4 w-4 flex-shrink-0", isActive ? "text-brand-blue" : "text-slate-400")} aria-hidden />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="border-t border-line p-4">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-blue to-brand-teal text-sm font-semibold text-white">
            {(userName ?? "P").slice(0, 1).toUpperCase()}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink">{userName ?? "Patient"}</p>
            <p className="text-xs text-ink-muted">Patient account</p>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function WorkspaceHeader({
  firstName,
  searchQuery,
  onSearchChange,
  attentionCount,
  onNavigate,
}: {
  firstName: string;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  /** Medicines due plus critical flags: what the patient should look at now. */
  attentionCount: number;
  onNavigate: (id: string) => void;
}) {
  return (
    <header id="dashboard" className="sticky top-0 z-20 border-b border-line bg-white/90 backdrop-blur-xl">
      <div className="flex flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between xl:px-8">
        <div className="flex items-center justify-between gap-3">
          <span className="xl:hidden">
            <NoraLogo />
          </span>
          <div className="hidden xl:block">
            <h1 className="text-lg font-semibold text-ink">{firstName ? `Welcome back, ${firstName}` : "Welcome back"}</h1>
            <p className="text-xs text-ink-muted">Your reports, vitals and medicines in one place.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <NotificationLink />
          <label className="relative flex-1 lg:w-80">
            <span className="sr-only">Search reports</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search reports by title, file or summary"
              className="form-field h-10 py-0 pl-9"
            />
          </label>
          <Button
            variant="secondary"
            size="sm"
            className="relative h-10 w-10 flex-shrink-0 px-0"
            onClick={() => onNavigate("medications")}
            aria-label={attentionCount > 0 ? `${attentionCount} items need attention: show today's medicines` : "Nothing needs attention right now"}
            icon={<Bell className="h-4 w-4" />}
          >
            {attentionCount > 0 ? (
              <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white">
                {attentionCount}
              </span>
            ) : null}
          </Button>
          <Button size="sm" className="h-10 flex-shrink-0" icon={<Plus className="h-4 w-4" />} onClick={() => onNavigate("appointments")}>
            <span className="hidden sm:inline">Book appointment</span>
            <span className="sm:hidden">Book</span>
          </Button>
        </div>
      </div>

      <nav aria-label="Dashboard sections" className="flex gap-2 overflow-x-auto px-4 pb-3 xl:hidden">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onNavigate(item.id)}
            className="inline-flex flex-shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border border-line bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-line-strong hover:text-ink"
          >
            <item.icon className="h-3.5 w-3.5" aria-hidden />
            {item.label}
          </button>
        ))}
      </nav>
    </header>
  );
}

export function QuickLinks() {
  return (
    <nav aria-label="Quick links" className="flex flex-wrap gap-2">
      {QUICK_LINKS.map((link) => (
        <ButtonLink key={link.href} href={link.href} variant="secondary" size="sm" icon={<link.icon className="h-3.5 w-3.5" />}>
          {link.label}
        </ButtonLink>
      ))}
    </nav>
  );
}

/** Account footer: who can see the records (true by design) and sign out. */
export function SettingsStrip({ onSignOut }: { onSignOut: () => void }) {
  return (
    <section id="settings" className="scroll-mt-24 rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-control bg-blue-50 text-brand-blue">
            <LockKeyhole className="h-5 w-5" aria-hidden />
          </span>
          <div>
            <h2 className="text-base font-semibold text-ink">Who can see your records</h2>
            <p className="mt-0.5 max-w-2xl text-sm leading-6 text-ink-muted">
              Only you, and a doctor while you have given them a one-time code. Doctor access ends when the consultation is ended
              or the code&apos;s access expires.
            </p>
          </div>
        </div>
        <div className="flex flex-shrink-0 flex-wrap gap-2">
          <ButtonLink href="/profile" variant="secondary" icon={<UserRound className="h-4 w-4" />}>
            My profile
          </ButtonLink>
          <Button variant="secondary" onClick={onSignOut} icon={<LogOut className="h-4 w-4" />}>
            Sign out
          </Button>
        </div>
      </div>
    </section>
  );
}
