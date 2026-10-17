"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { lookOf } from "@/lib/notifications";
import type { AppNotification } from "@/lib/types";

const VISIBLE_MS = 8000;

/**
 * Small, quiet pop-ups for notifications that arrive while the app is open. They announce themselves politely
 * to a screen reader, go away on their own after 8 seconds (not while the pointer or keyboard is on them), can be
 * closed, and open the page they are about (reading the notification on the way).
 */
export function NotificationToaster({ toasts, onDismiss }: { toasts: AppNotification[]; onDismiss: (id: number) => void }) {
  return (
    <div
      role="region"
      aria-label="New notifications"
      className="pointer-events-none fixed bottom-4 right-4 z-[70] flex w-[min(calc(100vw-2rem),22rem)] flex-col gap-2"
    >
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function Toast({ toast, onDismiss }: { toast: AppNotification; onDismiss: (id: number) => void }) {
  const { icon: Icon, tone } = lookOf(toast.kind);
  const [paused, setPaused] = useState(false);
  const timer = useRef(0);

  useEffect(() => {
    if (paused) return;
    timer.current = window.setTimeout(() => onDismiss(toast.id), VISIBLE_MS);
    return () => window.clearTimeout(timer.current);
  }, [paused, onDismiss, toast.id]);

  const open = () => {
    void api.markNotificationRead(toast.id).catch(() => undefined);
    onDismiss(toast.id);
  };
  const body = (
    <>
      <span className={cn("grid h-9 w-9 flex-shrink-0 place-items-center rounded-full", tone)}>
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <span className="min-w-0 flex-1 text-left">
        <span className="block break-words text-sm font-semibold text-ink">{toast.title}</span>
        <span className="mt-0.5 line-clamp-2 block break-words text-sm leading-5 text-ink-muted">{toast.body}</span>
      </span>
    </>
  );
  const row = "flex min-w-0 flex-1 items-start gap-3 rounded-l-card p-3.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue";

  return (
    <div
      role="status"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      className="pointer-events-auto flex items-start rounded-card border border-line bg-white shadow-card-hover motion-safe:animate-[toast-in_200ms_ease-out]"
    >
      {toast.link ? (
        <Link href={toast.link} onClick={open} className={row}>
          {body}
        </Link>
      ) : (
        <button type="button" onClick={open} className={row}>
          {body}
        </button>
      )}
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label={`Close: ${toast.title}`}
        className="m-2 grid h-7 w-7 flex-shrink-0 place-items-center rounded-control text-slate-400 hover:bg-surface-soft hover:text-ink"
      >
        <X className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}
