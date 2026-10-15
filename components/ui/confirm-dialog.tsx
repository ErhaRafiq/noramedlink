"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

/**
 * Confirmation for destructive actions, built on the native <dialog>: focus moves into it,
 * Escape and the backdrop cancel, and focus returns to the trigger when it closes.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  pendingLabel,
  pending = false,
  tone = "danger",
  confirmDisabled = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  pendingLabel?: string;
  pending?: boolean;
  tone?: "danger" | "primary";
  /** Keep the confirm button off until the form inside is complete. */
  confirmDisabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

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
        event.preventDefault(); // keep React state the source of truth
        if (!pending) onCancel();
      }}
      onClick={(event) => {
        if (event.target === ref.current && !pending) onCancel(); // click on the backdrop
      }}
      aria-labelledby="confirm-dialog-title"
      className="w-[calc(100%-2rem)] max-w-md rounded-card border border-line bg-white p-0 shadow-calm backdrop:bg-slate-950/40 backdrop:backdrop-blur-sm"
    >
      <div className="p-6">
        <h2 id="confirm-dialog-title" className="text-lg font-semibold text-ink">
          {title}
        </h2>
        <div className="mt-2 text-sm leading-6 text-ink-muted">{description}</div>
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={onCancel} disabled={pending}>
            Cancel
          </Button>
          <Button variant={tone} onClick={onConfirm} loading={pending} disabled={confirmDisabled}>
            {pending && pendingLabel ? pendingLabel : confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
