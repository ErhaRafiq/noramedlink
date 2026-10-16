"use client";

import Link from "next/link";
import { Bell } from "lucide-react";

import { cn } from "@/lib/cn";
import { useUnreadCount } from "@/hooks/notifications/use-unread-count";

/** A bell that opens the notifications page, with the unread count. Render it only for signed-in users. */
export function NotificationLink({ className, label = false }: { className?: string; label?: boolean }) {
  const unread = useUnreadCount(true);
  return (
    <Link
      href="/notifications"
      aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
      className={cn("relative inline-flex min-h-[36px] items-center justify-center gap-2 rounded-control px-2.5 text-slate-600 transition-colors hover:bg-surface-soft hover:text-ink", className)}
    >
      <Bell className="h-4 w-4" aria-hidden />
      {label ? <span className="text-sm font-medium">Notifications</span> : null}
      {unread > 0 ? (
        <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold leading-none text-white">
          {unread > 9 ? "9+" : unread}
        </span>
      ) : null}
    </Link>
  );
}
