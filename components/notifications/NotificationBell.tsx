"use client";

import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { Bell, BellOff, CheckCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";
import { useNotifications } from "@/hooks/notifications/use-notifications";
import { NotificationItem } from "./NotificationItem";
import { useNotificationCenter } from "./NotificationsProvider";

const PANEL_WIDTH = 384;
const MARGIN = 8;

/**
 * The bell: the unread count on it, and a panel with the latest notifications that opens in place. The panel is
 * not modal (the page behind stays usable), closes with Escape, a click outside or opening an item, and gives focus
 * back to the bell. In the sidebar (`label`) it opens beside the button instead of under it.
 */
export function NotificationBell({ className, label = false }: { className?: string; label?: boolean }) {
  const { unread } = useNotificationCenter();
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState<CSSProperties>({});

  const close = useCallback((returnFocus = true) => {
    setOpen(false);
    if (returnFocus) button.current?.focus();
  }, []);

  useLayoutEffect(() => {
    if (!open || !button.current) return;
    const rect = button.current.getBoundingClientRect();
    const width = Math.min(PANEL_WIDTH, window.innerWidth - MARGIN * 2);
    if (label) {
      // Beside the sidebar button, growing upwards from its bottom edge.
      const left = Math.min(rect.right + MARGIN, window.innerWidth - width - MARGIN);
      setStyle({ left, width, bottom: Math.max(MARGIN, window.innerHeight - rect.bottom), maxHeight: Math.min(560, rect.bottom - MARGIN) });
    } else {
      const left = Math.max(MARGIN, Math.min(rect.right - width, window.innerWidth - width - MARGIN));
      setStyle({ left, width, top: rect.bottom + MARGIN, maxHeight: Math.min(560, window.innerHeight - rect.bottom - MARGIN * 2) });
    }
  }, [label, open]);

  useEffect(() => {
    if (!open) return;
    panel.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!panel.current?.contains(target) && !button.current?.contains(target)) close(false);
    };
    const onResize = () => close(false);
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    window.addEventListener("resize", onResize);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("resize", onResize);
    };
  }, [close, open]);

  return (
    <>
      <button
        ref={button}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        className={cn(
          "relative inline-flex min-h-[36px] items-center justify-center gap-2 rounded-control px-2.5 text-slate-600 transition-colors hover:bg-surface-soft hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue",
          className,
        )}
      >
        <Bell className="h-4 w-4" aria-hidden />
        {label ? <span className="text-sm font-medium">Notifications</span> : null}
        {unread > 0 ? (
          <span
            aria-hidden
            className={cn(
              "grid h-4 min-w-4 place-items-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold leading-none text-white",
              label ? "ml-auto" : "absolute -right-0.5 -top-0.5",
            )}
          >
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>
      {open ? createPortal(<Panel panel={panel} style={style} onClose={() => close(false)} />, document.body) : null}
    </>
  );
}

function Panel({ panel, style, onClose }: { panel: React.RefObject<HTMLDivElement | null>; style: CSSProperties; onClose: () => void }) {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const list = useNotifications({ unreadOnly, pageSize: 8 });

  return (
    <div
      ref={panel}
      role="dialog"
      aria-label="Notifications"
      tabIndex={-1}
      style={{ position: "fixed", ...style }}
      className="z-[60] flex flex-col overflow-hidden rounded-card border border-line bg-white shadow-card-hover focus-visible:outline-none"
    >
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">Notifications</h2>
        <Button variant="ghost" size="sm" icon={<CheckCheck className="h-4 w-4" />} disabled={list.unread === 0} onClick={() => void list.markAllRead()}>
          Mark all read
        </Button>
      </div>
      <div role="tablist" aria-label="Show" className="flex gap-1 border-b border-line px-3 py-2">
        {[
          { id: false, label: "All" },
          { id: true, label: list.unread > 0 ? `Unread (${list.unread})` : "Unread" },
        ].map((tab) => (
          <button
            key={String(tab.id)}
            type="button"
            role="tab"
            aria-selected={unreadOnly === tab.id}
            onClick={() => setUnreadOnly(tab.id)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-semibold transition-colors",
              unreadOnly === tab.id ? "bg-blue-50 text-brand-blue" : "text-slate-500 hover:bg-surface-soft hover:text-ink",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {list.status === "loading" ? (
          <div role="status" aria-label="Loading notifications" className="space-y-3 p-4">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="flex gap-3">
                <Skeleton className="h-9 w-9 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3.5 w-1/2" />
                  <Skeleton className="h-3 w-5/6" />
                </div>
              </div>
            ))}
          </div>
        ) : list.status === "error" ? (
          <div className="p-5 text-center text-sm text-ink-muted">
            <p>{list.error}</p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={list.retry}>
              Try again
            </Button>
          </div>
        ) : list.items.length === 0 ? (
          <div className="px-6 py-10 text-center">
            <BellOff className="mx-auto h-6 w-6 text-slate-300" aria-hidden />
            <p className="mt-2 text-sm font-semibold text-ink">{unreadOnly ? "You are all caught up" : "Nothing here yet"}</p>
            <p className="mt-0.5 text-xs text-ink-muted">
              {unreadOnly ? "There is nothing you have not read." : "Bookings, reminders and updates will appear here."}
            </p>
          </div>
        ) : (
          <ul>
            {list.items.map((item) => (
              <NotificationItem key={item.id} item={item} compact onOpen={onClose} onRead={(id) => void list.markRead(id)} />
            ))}
          </ul>
        )}
      </div>

      <Link href="/notifications" onClick={onClose} className="border-t border-line px-4 py-3 text-center text-sm font-semibold text-brand-blue hover:bg-surface-soft">
        See all notifications
      </Link>
    </div>
  );
}
