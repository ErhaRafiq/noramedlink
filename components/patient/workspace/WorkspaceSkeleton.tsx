import { Skeleton, SkeletonCard } from "@/components/ui/skeleton";

/** Placeholder with the dashboard's shape while its data loads. */
export function WorkspaceSkeleton() {
  return (
    <div role="status" aria-label="Loading your health dashboard" className="flex min-h-screen bg-surface-page">
      <div className="hidden xl:block fixed inset-y-0 left-0 w-[264px] border-r border-line bg-white p-5">
        <Skeleton className="h-10 w-40" />
        <div className="mt-8 space-y-3">
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="h-9 w-full rounded-2xl" />
          ))}
        </div>
      </div>
      <div className="min-w-0 flex-1 xl:ml-[264px] p-4 sm:p-6 xl:p-8 space-y-5">
        <div className="flex items-center justify-between rounded-2xl bg-white/80 p-4">
          <div className="space-y-2">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-3 w-64" />
          </div>
          <Skeleton className="hidden h-10 w-72 sm:block" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <SkeletonCard key={i} lines={3} />
          ))}
        </div>
        <SkeletonCard lines={2} />
        <div className="grid gap-5 xl:grid-cols-2">
          <SkeletonCard lines={5} />
          <SkeletonCard lines={5} />
        </div>
      </div>
      <span className="sr-only">Loading your health dashboard...</span>
    </div>
  );
}
