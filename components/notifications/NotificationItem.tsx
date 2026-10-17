"use client";

import Link from "next/link";
import { X } from "lucide-react";

import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/datetime";
import { lookOf, relativeTime } from "@/lib/notifications";
import type { AppNotification } from "@/lib/types";

/**
 * One notification. The whole row is a link when the notification leads somewhere (and reads it on the way),
 * otherwise a button that marks it read. Unread ones have a blue dot and a stronger background, and say
 * "(unread)" to a screen reader. The full page also shows "Mark read" and "Dismiss" buttons, which are always
 * visible so they work on a phone without hovering.
 */
export function NotificationItem({
  item,
  compact = false,
  onOpen,
  onRead,
  onDismiss,
}: {
  item: AppNotification;
  compact?: boolean;
  /** Called when the row is opened (the panel closes itself here). */
  onOpen?: () => void;
  onRead: (id: number) => void;
  onDismiss?: (id: number) => void;
}) {
  const { icon: Icon, tone } = lookOf(item.kind);
  const content = (
    <>
      <span className={cn("grid h-9 w-9 flex-shrink-0 place-items-center rounded-full", item.read ? "bg-surface-soft text-slate-400" : tone)}>
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <span className="min-w-0 flex-1 text-left">
        <span className={cn("block break-words text-sm text-ink", item.read ? "font-medium" : "font-semibold")}>
          {item.title}
          {item.read ? null : <span className="sr-only"> (unread)</span>}
        </span>
        <span className={cn("mt-0.5 block break-words text-sm leading-5 text-ink-muted", compact && "line-clamp-2")}>{item.body}</span>
        <time dateTime={item.at} title={formatDateTime(item.at)} className="mt-1 block text-xs text-slate-400">
          {relativeTime(item.at)}
        </time>
      </span>
      {item.read ? null : <span aria-hidden className="mt-2 h-2.5 w-2.5 flex-shrink-0 rounded-full bg-brand-blue" />}
    </>
  );
  const row = cn(
    "flex w-full min-w-0 items-start gap-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue",
    compact ? "px-4 py-3 hover:bg-surface-soft" : "rounded-card p-4",
  );
  const open = () => {
    onRead(item.id);
    onOpen?.();
  };

  return (
    <li className={cn(compact ? "border-b border-line last:border-b-0" : "rounded-card border shadow-card", !compact && (item.read ? "border-line bg-white" : "border-blue-200 bg-blue-50/50"), compact && !item.read && "bg-blue-50/40")}>
      <div className="flex items-start">
        {item.link ? (
          <Link href={item.link} onClick={open} className={row}>
            {content}
          </Link>
        ) : (
          <button type="button" onClick={open} className={row}>
            {content}
          </button>
        )}
        {!compact ? (
          <div className="flex flex-shrink-0 flex-col items-end gap-1 py-3 pr-3">
            {item.read ? null : (
              <button type="button" onClick={() => onRead(item.id)} className="rounded-control px-2 py-1 text-xs font-medium text-slate-500 hover:bg-surface-soft hover:text-ink">
                Mark read
              </button>
            )}
            {onDismiss ? (
              <button
                type="button"
                onClick={() => onDismiss(item.id)}
                aria-label={`Dismiss: ${item.title}`}
                className="grid h-7 w-7 place-items-center rounded-control text-slate-400 hover:bg-surface-soft hover:text-ink"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </li>
  );
}
