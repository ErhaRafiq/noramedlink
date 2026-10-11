import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

export type AlertTone = "info" | "success" | "warning" | "error";

const tones: Record<AlertTone, { box: string; icon: LucideIcon; iconClass: string }> = {
  info: { box: "border-blue-100 bg-blue-50 text-blue-900", icon: Info, iconClass: "text-blue-600" },
  success: { box: "border-emerald-100 bg-emerald-50 text-emerald-900", icon: CheckCircle2, iconClass: "text-emerald-600" },
  warning: { box: "border-amber-200 bg-amber-50 text-amber-900", icon: AlertTriangle, iconClass: "text-amber-600" },
  error: { box: "border-rose-100 bg-rose-50 text-rose-900", icon: XCircle, iconClass: "text-rose-600" },
};

/**
 * Inline status message. Errors are announced immediately (role="alert"); other tones
 * politely (role="status").
 */
export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: AlertTone;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  const { box, icon: Icon, iconClass } = tones[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("flex gap-3 rounded-control border px-4 py-3 text-sm", box, className)}>
      <Icon className={cn("mt-0.5 h-4 w-4 flex-shrink-0", iconClass)} aria-hidden />
      <div className="min-w-0 leading-6">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className={title ? "mt-0.5" : undefined}>{children}</div> : null}
      </div>
    </div>
  );
}
