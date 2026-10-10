"use client";

import type { ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";
import type { ToastState } from "@/hooks/use-toast";

export function DashCard({ children, className, id }: { children: ReactNode; className?: string; id?: string }) {
  return (
    <div
      id={id}
      className={cn(
        "rounded-3xl bg-white/80 backdrop-blur-xl border border-blue-100/70 shadow-[0_12px_40px_rgba(30,64,175,0.08)] p-5",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function MiniVital({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div className="h-6 w-6 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
          <Icon className="h-3 w-3 text-blue-500" />
        </div>
        <span className="text-xs font-semibold text-slate-500">{label}</span>
      </div>
      <span className="text-xs font-black text-slate-900">{value}</span>
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
          className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50"
          role="status"
          aria-live="polite"
        >
          <div
            className={cn(
              "rounded-full px-5 py-3 text-sm font-semibold shadow-xl backdrop-blur-xl border",
              toast.type === "success"
                ? "bg-emerald-50 text-emerald-800 border-emerald-100"
                : toast.type === "error"
                  ? "bg-rose-50 text-rose-800 border-rose-100"
                  : "bg-blue-50 text-blue-800 border-blue-100",
            )}
          >
            {toast.message}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
