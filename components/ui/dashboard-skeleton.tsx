import { Skeleton, SkeletonCard } from "@/components/ui/skeleton";

/**
 * Loading placeholder for the sidebar dashboards (doctor, admin): a dark sidebar, a
 * header card, four stat cards and two rows of content cards.
 */
export function SidebarDashboardSkeleton({ label }: { label: string }) {
  return (
    <main role="status" aria-label={label} className="app-shell min-h-screen">
      <div className="mx-auto grid max-w-[1520px] gap-6 px-4 py-5 lg:grid-cols-[286px_1fr] lg:px-6">
        <div className="nm-sidebar hidden h-[560px] lg:block">
          <Skeleton className="h-10 w-40 bg-white/15" />
          <div className="mt-8 space-y-3">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-10 w-full bg-white/10" />
            ))}
          </div>
        </div>
        <div className="space-y-6">
          <div className="dashboard-topbar space-y-3">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-8 w-72" />
            <Skeleton className="h-3 w-96 max-w-full" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <SkeletonCard key={i} lines={2} />
            ))}
          </div>
          <div className="grid gap-6 xl:grid-cols-2">
            <SkeletonCard lines={5} />
            <SkeletonCard lines={5} />
          </div>
        </div>
      </div>
      <span className="sr-only">{label}</span>
    </main>
  );
}
