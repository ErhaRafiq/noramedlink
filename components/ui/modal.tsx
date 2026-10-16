"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

import { cn } from "@/lib/cn";

/**
 * A dialog for forms and pickers, built on the native <dialog>: focus moves into it, Escape and the
 * backdrop close it, focus returns to the trigger afterwards, and the page behind cannot be tapped.
 * `busy` blocks closing while a request is in flight. (Destructive confirmations use ConfirmDialog.)
 */
export function Modal({
  open,
  title,
  description,
  onClose,
  busy = false,
  wide = false,
  footer,
  children,
}: {
  open: boolean;
  title: string;
  description?: ReactNode;
  onClose: () => void;
  busy?: boolean;
  wide?: boolean;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onCancel={(event) => {
        event.preventDefault(); // React state stays the source of truth
        if (!busy) onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current && !busy) onClose(); // click on the backdrop
      }}
      aria-labelledby={titleId}
      className={cn(
        "m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-1.5rem)] overflow-hidden rounded-card border border-line bg-white p-0 shadow-calm backdrop:bg-slate-950/40 backdrop:backdrop-blur-sm",
        wide ? "max-w-2xl" : "max-w-md",
      )}
    >
      {open ? (
        <div className="flex max-h-[calc(100dvh-2rem)] flex-col">
          <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4 sm:px-6">
            <div className="min-w-0">
              <h2 id={titleId} className="break-words text-lg font-semibold text-ink">
                {title}
              </h2>
              {description ? <p className="mt-0.5 text-sm text-ink-muted">{description}</p> : null}
            </div>
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              aria-label="Close"
              className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-control text-slate-500 transition-colors hover:bg-surface-soft hover:text-ink disabled:opacity-50"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 sm:px-6">{children}</div>
          {footer ? <div className="flex flex-col-reverse gap-2 border-t border-line px-5 py-4 sm:flex-row sm:justify-end sm:px-6">{footer}</div> : null}
        </div>
      ) : null}
    </dialog>
  );
}
