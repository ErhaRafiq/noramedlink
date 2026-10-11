"use client";

import type { ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";
import type { ToastState } from "@/hooks/use-toast";

/** The dashboard card: same look as the shared Card component. */
export function DashCard({ children, className, id }: { children: ReactNode; className?: string; id?: string }) {
  return (
    <div id={id} className={cn("min-w-0 scroll-mt-24 rounded-card border border-line bg-white p-5 shadow-card sm:p-6", className)}>
      {children}
    </div>
  );
}

export function MiniVital({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  const missing = value === "Not recorded";
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-2 text-xs text-ink-muted">
        <Icon className="h-3.5 w-3.5 text-slate-400" aria-hidden />
        {label}
      </span>
      <span className={cn("text-xs font-semibold", missing ? "text-slate-400" : "text-ink")}>{value}</span>
    </div>
  );
}

export function ToastBar({ toast }: { toast: ToastState }) {
  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 16 }}
          className="fixed bottom-5 left-1/2 z-50 -translate-x-1/2 px-4"
          role="status"
          aria-live="polite"
        >
          <div
            className={cn(
              "rounded-control border px-4 py-3 text-sm font-medium shadow-card-hover",
              toast.type === "success"
                ? "border-emerald-100 bg-emerald-50 text-emerald-900"
                : toast.type === "error"
                  ? "border-rose-100 bg-rose-50 text-rose-900"
                  : "border-blue-100 bg-blue-50 text-blue-900",
            )}
          >
            {toast.message}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
