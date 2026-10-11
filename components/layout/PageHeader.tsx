import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/** Page width and padding shared by the standalone pages (doctors, payments, ...). */
export function PageContainer({ children, className, narrow = false }: { children: ReactNode; className?: string; narrow?: boolean }) {
  return <div className={cn("mx-auto w-full px-4 py-8 sm:px-6 lg:py-10", narrow ? "max-w-4xl" : "max-w-6xl", className)}>{children}</div>;
}

/** Eyebrow, title, description and optional actions at the top of a page. */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        {eyebrow ? <p className="section-eyebrow">{eyebrow}</p> : null}
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">{title}</h1>
        {description ? <p className="mt-3 text-sm leading-6 text-ink-muted sm:text-base">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}
