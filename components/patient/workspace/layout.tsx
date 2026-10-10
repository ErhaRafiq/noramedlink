"use client";

import Link from "next/link";
import {
  Activity,
  Bell,
  CalendarDays,
  ChevronRight,
  FileText,
  HeartPulse,
  Home,
  KeyRound,
  LogOut,
  Pill,
  Plus,
  Search,
  Settings,
  Shield,
  Siren,
  Sparkles,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/cn";

export const NAV_ITEMS: Array<{ id: string; label: string; icon: LucideIcon }> = [
  { id: "dashboard", label: "Dashboard", icon: Home },
  { id: "reports", label: "My Reports", icon: FileText },
  { id: "vitals", label: "Vitals", icon: Activity },
  { id: "medications", label: "Medications", icon: Pill },
  { id: "appointments", label: "Appointments", icon: CalendarDays },
  { id: "insights", label: "Health Insights", icon: HeartPulse },
  { id: "reminders", label: "Reminders", icon: Bell },
  { id: "care-team", label: "Doctor Access", icon: KeyRound },
  { id: "settings", label: "Settings", icon: Settings },
];

const QUICK_LINKS: Array<{ href: string; label: string; icon: LucideIcon }> = [
  { href: "/doctors", label: "Find a doctor", icon: Stethoscope },
  { href: "/summarize", label: "Summarize a report", icon: Sparkles },
  { href: "/emergency", label: "Emergency / home visit", icon: Siren },
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
    <aside className="hidden xl:flex flex-col fixed inset-y-0 left-0 w-[280px] bg-white/95 backdrop-blur-xl border-r border-blue-100/70 shadow-[4px_0_24px_rgba(30,64,175,0.06)] z-30">
      <div className="p-5 border-b border-blue-50/80">
        <Link href="/" className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-md shadow-blue-200/50 flex-shrink-0">
            <HeartPulse className="h-5 w-5 text-white" />
          </div>
          <div className="text-left">
            <p className="text-sm font-black text-slate-900">Nora MedLink</p>
            <p className="text-[11px] text-slate-400 font-medium">Patient Portal</p>
          </div>
        </Link>
      </div>

      <nav aria-label="Dashboard sections" className="flex-1 p-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = activeNav === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              aria-current={isActive ? "true" : undefined}
              className={cn(
                "w-full flex items-center gap-3 px-4 py-2.5 rounded-2xl text-sm font-semibold transition-all duration-200 text-left",
                isActive
                  ? "bg-gradient-to-r from-blue-600 to-violet-600 text-white shadow-lg shadow-blue-200/40"
                  : "text-slate-600 hover:bg-blue-50 hover:text-blue-700",
              )}
            >
              <item.icon className={cn("h-4 w-4 flex-shrink-0", isActive ? "text-white" : "text-slate-400")} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="mx-4 mb-4 p-3.5 rounded-2xl bg-blue-50/80 border border-blue-100">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-blue-500 to-violet-500 flex items-center justify-center text-white font-black text-sm flex-shrink-0">
            {(userName ?? "P").slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-black text-slate-900 truncate">{userName ?? "Patient"}</p>
            <button
              type="button"
              onClick={() => onNavigate("settings")}
              className="text-[11px] text-blue-600 font-semibold hover:text-blue-700 flex items-center gap-0.5 mt-0.5 transition"
            >
              View Profile <ChevronRight className="h-3 w-3" />
            </button>
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
  unreadCount,
  onNavigate,
}: {
  firstName: string;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  unreadCount: number;
  onNavigate: (id: string) => void;
}) {
  return (
    <header
      id="dashboard"
      className="sticky top-0 z-20 bg-white/95 backdrop-blur-xl border-b border-blue-100/70 shadow-[0_4px_20px_rgba(30,64,175,0.06)]"
    >
      <div className="px-4 xl:px-6 py-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-lg font-black text-slate-900">{firstName ? `Welcome back, ${firstName}` : "Welcome back"}</h1>
          <p className="text-xs text-slate-500 mt-0.5">Here&apos;s your personalized health overview for today.</p>
        </div>
        <div className="flex items-center gap-2.5">
          <div className="relative flex-1 lg:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
            <input
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              aria-label="Search reports"
              placeholder="Search reports by title, file or summary"
              className="w-full h-10 pl-10 pr-4 rounded-xl border border-blue-100 bg-blue-50/50 text-sm text-slate-900 outline-none focus:border-blue-300 focus:bg-white focus:ring-4 focus:ring-blue-100 placeholder:text-slate-400 transition"
            />
          </div>
          <button
            type="button"
            onClick={() => onNavigate("appointments")}
            className="h-10 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 text-white text-sm font-bold shadow-md shadow-blue-200/50 hover:-translate-y-0.5 transition-transform flex items-center gap-1.5 whitespace-nowrap flex-shrink-0"
          >
            <Plus className="h-4 w-4" />
            Book Appointment
          </button>
          <button
            type="button"
            aria-label={`${unreadCount} items need attention`}
            className="relative h-10 w-10 rounded-xl border border-blue-100 bg-white flex items-center justify-center text-slate-600 hover:border-blue-200 hover:text-blue-600 transition flex-shrink-0"
          >
            <Bell className="h-4 w-4" />
            <span className="absolute -right-1 -top-1 h-5 w-5 rounded-full bg-rose-500 text-[9px] font-black text-white flex items-center justify-center">
              {unreadCount}
            </span>
          </button>
        </div>
      </div>

      <div className="xl:hidden px-4 pb-3 flex gap-2 overflow-x-auto scrollbar-hide">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onNavigate(item.id)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-blue-100 bg-white text-xs font-semibold text-slate-600 hover:border-blue-300 hover:text-blue-700 transition whitespace-nowrap flex-shrink-0"
          >
            <item.icon className="h-3.5 w-3.5" />
            {item.label}
          </button>
        ))}
      </div>
    </header>
  );
}

export function QuickLinks() {
  return (
    <nav aria-label="Quick links" className="flex flex-wrap gap-2">
      {QUICK_LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className="inline-flex items-center gap-1.5 rounded-xl border border-blue-100 bg-white px-3.5 py-2 text-xs font-bold text-slate-600 hover:border-blue-300 hover:text-blue-700 transition"
        >
          <link.icon className="h-3.5 w-3.5" />
          {link.label}
        </Link>
      ))}
    </nav>
  );
}

export function SettingsStrip({ onSignOut }: { onSignOut: () => void }) {
  return (
    <section id="settings">
      <div className="rounded-2xl bg-gradient-to-r from-blue-600 via-indigo-600 to-violet-600 p-5 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-lg shadow-blue-200/50">
        <div className="flex items-center gap-4">
          <div className="h-10 w-10 rounded-xl bg-white/20 flex items-center justify-center flex-shrink-0">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <div>
            <p className="text-sm font-black text-white">Your privacy is our priority</p>
            <p className="text-xs text-blue-100 mt-0.5">
              All your data is encrypted and secure. We never share your health information.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <button
            type="button"
            onClick={onSignOut}
            className="px-4 py-2 rounded-xl bg-white/20 border border-white/30 text-white text-sm font-bold hover:bg-white/30 transition flex items-center gap-2"
          >
            <LogOut className="h-4 w-4" /> Sign Out
          </button>
        </div>
      </div>
    </section>
  );
}
