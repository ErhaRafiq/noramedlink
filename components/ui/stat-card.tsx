import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";
import { Skeleton } from "@/components/ui/skeleton";

/** A single number with a label, used in dashboard summary rows. */
export function StatCard({
  label,
  value,
  detail,
  icon: Icon,
  tint = "bg-blue-50 text-brand-blue",
}: {
  label: string;
  value: ReactNode;
  detail?: string;
  icon: LucideIcon;
  tint?: string;
}) {
  return (
    <article className="min-w-0 rounded-card border border-line bg-white p-5 shadow-card">
      <div className="flex items-center gap-3">
        <span className={cn("grid h-9 w-9 flex-shrink-0 place-items-center rounded-control", tint)}>
          <Icon className="h-4 w-4" aria-hidden />
        </span>
        <p className="text-sm font-medium text-ink-muted">{label}</p>
      </div>
      <p className="mt-4 text-3xl font-semibold tracking-tight text-ink">{value}</p>
      {detail ? <p className="mt-1 text-xs text-ink-muted">{detail}</p> : null}
    </article>
  );
}

export function StatCardSkeleton() {
  return (
    <div className="rounded-card border border-line bg-white p-5 shadow-card">
      <div className="flex items-center gap-3">
        <Skeleton className="h-9 w-9" />
        <Skeleton className="h-3 w-24" />
      </div>
      <Skeleton className="mt-4 h-7 w-16" />
      <Skeleton className="mt-2 h-3 w-28" />
    </div>
  );
}
