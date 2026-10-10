import { cn } from "@/lib/cn";

/** Placeholder block shown while data loads. Purely visual: hidden from screen readers. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-control bg-slate-200/70", className)} />;
}

/** A card-shaped loading placeholder with a title line and `lines` text lines. */
export function SkeletonCard({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("rounded-card border border-line bg-white p-5 shadow-card sm:p-6", className)}>
      <Skeleton className="h-4 w-32" />
      <div className="mt-5 space-y-3">
        {Array.from({ length: lines }, (_, i) => (
          <Skeleton key={i} className={cn("h-3", i === lines - 1 ? "w-2/3" : "w-full")} />
        ))}
      </div>
    </div>
  );
}
