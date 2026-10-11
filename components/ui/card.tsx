import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, interactive = false, ...props }: ComponentProps<"section"> & { interactive?: boolean }) {
  return (
    <section
      className={cn("min-w-0 scroll-mt-24 rounded-card border border-line bg-white p-5 shadow-card sm:p-6", interactive && "floating-card", className)}
      {...props}
    />
  );
}

/** Card heading row: optional eyebrow, a title, and an optional action on the right. */
export function CardHeader({
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-5 flex items-start justify-between gap-4", className)}>
      <div className="min-w-0">
        {eyebrow ? <p className="section-eyebrow">{eyebrow}</p> : null}
        <h2 className={cn("text-lg font-semibold text-ink", eyebrow && "mt-1.5")}>{title}</h2>
        {description ? <p className="mt-1 text-sm leading-6 text-ink-muted">{description}</p> : null}
      </div>
      {action ? <div className="flex-shrink-0">{action}</div> : null}
    </div>
  );
}
