"use client";

import { ArrowRight, ChevronRight, Download, X } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/cn";
import { DEPARTMENTS, type DepartmentSlug } from "@/lib/departments";
import { validationLabel } from "@/lib/patient-dashboard";
import type { DepartmentTile, MedicalDocument } from "@/lib/types";
import type { useReportList } from "@/hooks/patient/use-report-list";
import { departmentIcon, formatDate, getDepartmentMeta } from "./helpers";
import { DashCard } from "./ui";

type ReportList = ReturnType<typeof useReportList>;

export function HealthCategoriesCard({
  tiles,
  activeDepartment,
  onSelect,
}: {
  tiles: DepartmentTile[];
  activeDepartment: DepartmentSlug | null;
  onSelect: (department: DepartmentSlug) => void;
}) {
  const counts = new Map(tiles.map((tile) => [tile.slug, tile.total_reports]));

  return (
    <section id="reports">
      <DashCard>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-ink">Health Categories</h2>
        </div>
        <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 xl:grid-cols-6">
          {DEPARTMENTS.map((department) => {
            const meta = getDepartmentMeta(department.slug);
            const count = counts.get(department.slug) ?? 0;
            const isActive = activeDepartment === department.slug;
            return (
              <button
                key={department.slug}
                type="button"
                aria-pressed={isActive}
                onClick={() => onSelect(department.slug)}
                className={cn(
                  "group rounded-2xl border p-3.5 text-left transition-all duration-200",
                  isActive ? "border-blue-300 bg-blue-50" : "border-slate-100 bg-slate-50/80 hover:border-blue-200 hover:bg-blue-50/60",
                )}
              >
                <div className={cn("h-10 w-10 rounded-xl flex items-center justify-center text-white shadow-md mb-3", `bg-gradient-to-br ${meta.gradient}`)}>
                  {departmentIcon(department.slug)}
                </div>
                <p className="text-sm font-semibold text-ink truncate">{department.label}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {count} {count === 1 ? "Document" : "Documents"}
                </p>
              </button>
            );
          })}
        </div>
      </DashCard>
    </section>
  );
}

function validationBadge(status: MedicalDocument["validation_status"]) {
  if (status === "HIGH_RISK") return { label: "Review", tone: "bg-rose-50 text-rose-600 border border-rose-100" };
  if (status === "CAUTION") return { label: "Monitor", tone: "bg-amber-50 text-amber-600 border border-amber-100" };
  return { label: validationLabel(status), tone: "bg-slate-100 text-slate-600 border border-slate-200" };
}

function ReportRowSkeleton() {
  return (
    <div className="flex items-center gap-3 p-3 rounded-2xl border border-slate-100 bg-white">
      <Skeleton className="h-9 w-9 rounded-xl" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3.5 w-2/3" />
        <Skeleton className="h-3 w-1/3" />
      </div>
      <Skeleton className="h-6 w-20 rounded-full" />
    </div>
  );
}

export function RecentReportsCard({
  list,
  activeDepartment,
  search,
  onClearFilters,
  onOpen,
  onDownload,
}: {
  list: ReportList;
  activeDepartment: DepartmentSlug | null;
  search: string;
  onClearFilters: () => void;
  onOpen: (report: MedicalDocument) => void;
  onDownload: (report: MedicalDocument) => void;
}) {
  const filtered = activeDepartment !== null || search.trim() !== "";
  const showSkeleton = list.isLoading && list.items.length === 0;

  return (
    <DashCard id="recent-reports">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h2 className="text-base font-semibold text-ink">
          {filtered ? "Matching Reports" : "Recent Reports"}
          {activeDepartment && <span className="font-semibold text-slate-400"> · {getDepartmentMeta(activeDepartment).label}</span>}
          {!list.isLoading && <span className="font-semibold text-slate-400"> · {list.total}</span>}
        </h2>
        <div className="flex items-center gap-2">
          {list.isLoading && !showSkeleton ? <Spinner className="h-3.5 w-3.5 text-blue-500" label="Updating reports" /> : null}
          {filtered && (
            <button type="button" onClick={onClearFilters} className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition">
              <X className="h-3 w-3" /> Clear filter
            </button>
          )}
        </div>
      </div>

      <div className={cn("space-y-2 transition-opacity", list.isLoading && !showSkeleton && "opacity-60")} aria-busy={list.isLoading}>
        {showSkeleton ? (
          Array.from({ length: 3 }, (_, i) => <ReportRowSkeleton key={i} />)
        ) : list.error ? (
          <p role="alert" className="p-3 text-sm text-rose-600">
            {list.error}
          </p>
        ) : list.items.length === 0 ? (
          <p className="p-3 text-sm text-slate-500">{filtered ? "No reports match this search." : "No reports uploaded yet."}</p>
        ) : (
          list.items.map((r) => {
            const meta = getDepartmentMeta(r.department_slug ?? r.category);
            const badge = validationBadge(r.validation_status);
            return (
              <div
                key={r.id}
                role="button"
                tabIndex={0}
                onClick={() => onOpen(r)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onOpen(r);
                  }
                }}
                className="flex cursor-pointer items-center gap-3 p-3 rounded-2xl border border-slate-100 bg-white hover:border-blue-100 hover:bg-blue-50/30 transition group"
              >
                <div className={cn("h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0 text-white", `bg-gradient-to-br ${meta.gradient}`)}>
                  {departmentIcon(meta.slug)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-ink truncate">{r.title}</p>
                  <p className="text-xs text-slate-400">
                    {meta.label} · {formatDate(r.upload_date)}
                  </p>
                </div>
                <span className={cn("text-[11px] font-semibold px-2.5 py-1 rounded-full flex-shrink-0", badge.tone)}>{badge.label}</span>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDownload(r);
                  }}
                  aria-label={`Download ${r.title}`}
                  className="h-7 w-7 rounded-lg border border-slate-200 bg-white flex items-center justify-center text-slate-400 hover:text-blue-600 hover:border-blue-200 transition opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                >
                  <Download className="h-3.5 w-3.5" />
                </button>
                <ChevronRight className="h-4 w-4 text-slate-300 transition group-hover:text-blue-500" />
              </div>
            );
          })
        )}
      </div>

      {list.hasMore && (
        <button
          type="button"
          onClick={() => void list.loadMore()}
          disabled={list.isLoadingMore}
          className="mt-3 w-full py-2.5 rounded-xl border border-blue-100 bg-blue-50/50 text-sm font-semibold text-blue-600 hover:bg-blue-50 transition flex items-center justify-center gap-2 disabled:opacity-70"
        >
          {list.isLoadingMore ? <Spinner className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
          {list.isLoadingMore ? "Loading..." : `Load more (${list.items.length} of ${list.total})`}
        </button>
      )}
    </DashCard>
  );
}
