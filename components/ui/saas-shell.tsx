"use client";

import Link from "next/link";
import type { ButtonHTMLAttributes, ElementType, ReactNode } from "react";
import { ShieldCheck } from "lucide-react";

import { NoraLogo } from "@/components/ui/NoraLogo";

type IconType = ElementType<{ className?: string }>;

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export type SidebarItem = {
  href: string;
  label: string;
  icon: IconType;
  active?: boolean;
};

export function AppShell({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <main className={cn("app-shell min-h-screen px-4 py-5 sm:px-6 lg:px-8", className)}>
      {children}
    </main>
  );
}

export function Sidebar({
  items,
  userName,
  userMeta,
  action,
}: {
  items: SidebarItem[];
  userName?: string;
  userMeta?: string;
  action?: ReactNode;
}) {
  return (
    <aside className="nm-sidebar h-fit lg:sticky lg:top-5">
      <NoraLogo inverse />

      {userName || userMeta ? (
        <div className="mt-7 rounded-[18px] border border-white/10 bg-white/[0.08] p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-teal-100">
            Signed in
          </p>
          {userName ? <p className="mt-2 truncate text-sm font-black text-white">{userName}</p> : null}
          {userMeta ? <p className="mt-1 truncate text-xs font-semibold text-slate-300">{userMeta}</p> : null}
        </div>
      ) : null}

      <nav className="mt-6 grid gap-2">
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn("nm-sidebar-item", item.active && "nm-sidebar-item-active")}
          >
            <item.icon className="h-4 w-4" />
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>

      {action ? <div className="mt-3">{action}</div> : null}

      <div className="mt-7 rounded-[18px] border border-teal-300/20 bg-teal-300/[0.08] p-4">
        <div className="flex items-center gap-2 text-teal-100">
          <ShieldCheck className="h-4 w-4" />
          <p className="text-xs font-black uppercase tracking-[0.14em]">Secure Access</p>
        </div>
        <p className="mt-2 text-xs font-semibold leading-5 text-slate-300">
          All actions are protected and audited.
        </p>
      </div>
    </aside>
  );
}

export function DashboardCard({
  children,
  className,
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return <section id={id} className={cn("dashboard-panel", className)}>{children}</section>;
}

export function StatCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: ReactNode;
  detail?: string;
  icon: IconType;
}) {
  return (
    <article className="metric-card">
      <div className="mb-4 flex items-start justify-between gap-4">
        <span className="grid h-11 w-11 place-items-center rounded-2xl bg-blue-50 text-blue-700 ring-1 ring-blue-100">
          <Icon className="h-5 w-5" />
        </span>
        <span className="h-2 w-14 rounded-full bg-gradient-to-r from-[#2563EB] to-[#00BFA6]" />
      </div>
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-black tracking-tight text-slate-950">{value}</p>
      {detail ? <p className="mt-1 text-xs font-semibold text-slate-400">{detail}</p> : null}
    </article>
  );
}

export function GradientButton({
  children,
  href,
  className,
  ...buttonProps
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  href?: string;
  className?: string;
}) {
  if (href) {
    return (
      <Link href={href} className={cn("gradient-button", className)}>
        {children}
      </Link>
    );
  }

  return (
    <button className={cn("gradient-button", className)} {...buttonProps}>
      {children}
    </button>
  );
}

export function RoleCard({
  title,
  description,
  selected,
  onClick,
}: {
  title: string;
  description: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "min-h-[122px] rounded-[18px] border p-4 text-left transition",
        selected
          ? "border-teal-300 bg-teal-50 text-teal-950 shadow-[0_12px_30px_rgba(0,191,166,0.12)] ring-4 ring-teal-100"
          : "border-[#DCE8F5] bg-white text-slate-700 hover:border-teal-200 hover:bg-[#F8FBFF]",
      )}
    >
      <span className="block text-sm font-black">{title}</span>
      <span className="mt-2 block text-xs font-semibold leading-5 text-slate-500">{description}</span>
    </button>
  );
}

export function FeatureCard({
  title,
  description,
  icon: Icon,
  href,
}: {
  title: string;
  description: string;
  icon: IconType;
  href: string;
}) {
  return (
    <Link href={href} className="feature-glass floating-card group flex h-full flex-col rounded-[20px] p-6">
      <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-700 ring-1 ring-blue-100">
        <Icon className="h-6 w-6" />
      </span>
      <h3 className="mt-6 text-lg font-black tracking-tight text-slate-950">{title}</h3>
      <p className="mt-3 text-sm leading-6 text-slate-600">{description}</p>
      <span className="mt-auto pt-7 text-sm font-bold text-blue-700">Open</span>
    </Link>
  );
}
