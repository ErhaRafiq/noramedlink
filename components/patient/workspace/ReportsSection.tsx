"use client";

import { useMemo, useState } from "react";
import { ArrowRight, ChevronRight, Download, Shield } from "lucide-react";

import { cn } from "@/lib/cn";
import { validationLabel, type ReportCategoryId } from "@/lib/patient-dashboard";
import type { HealthRiskPrediction, MedicalDocument } from "@/lib/types";
import {
  categoryIcon,
  countReportsByCategory,
  formatDate,
  getCategoryMeta,
  REPORTS_PREVIEW,
  RISKS_PREVIEW,
  scrollToSection,
} from "./helpers";
import { DashCard } from "./ui";

export function HealthCategoriesCard({
  reports,
  onSelect,
}: {
  reports: MedicalDocument[];
  onSelect: (category: ReportCategoryId) => void;
}) {
  const categories = useMemo(() => countReportsByCategory(reports), [reports]);

  return (
    <section id="reports">
      <DashCard>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-sm font-black text-slate-900">Health Categories</h2>
        </div>
        <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 xl:grid-cols-6">
          {categories.map((cat) => {
            const meta = getCategoryMeta(cat.id);
            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => {
                  onSelect(cat.id);
                  scrollToSection("recent-reports");
                }}
                className="group rounded-2xl border border-slate-100 bg-slate-50/80 p-3.5 text-left hover:border-blue-200 hover:bg-blue-50/60 hover:-translate-y-0.5 transition-all duration-200"
              >
                <div className={cn("h-10 w-10 rounded-xl flex items-center justify-center text-white shadow-md mb-3", `bg-gradient-to-br ${meta.style.gradient}`)}>
                  {categoryIcon(cat.id)}
                </div>
                <p className="text-sm font-bold text-slate-900 truncate">{cat.label}</p>
                <p className="text-xs text-slate-400 mt-0.5">{cat.count} Documents</p>
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
  if (status === "NOT_VALIDATED") return { label: validationLabel(status), tone: "bg-slate-100 text-slate-600 border border-slate-200" };
  return { label: "AI summarized", tone: "bg-blue-50 text-blue-600 border border-blue-100" };
}

export function RecentReportsCard({
  totalReports,
  filteredReports,
  activeCategory,
  onShowAll,
  onOpen,
  onDownload,
}: {
  totalReports: number;
  filteredReports: MedicalDocument[];
  activeCategory: ReportCategoryId | "all";
  onShowAll: () => void;
  onOpen: (report: MedicalDocument) => void;
  onDownload: (report: MedicalDocument) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? filteredReports : filteredReports.slice(0, REPORTS_PREVIEW);
  const canShowMore = activeCategory !== "all" || (!showAll && filteredReports.length > REPORTS_PREVIEW);

  return (
    <DashCard id="recent-reports">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-black text-slate-900">
          Recent Reports
          {activeCategory !== "all" && <span className="font-semibold text-slate-400"> · {getCategoryMeta(activeCategory).label}</span>}
        </h2>
        {canShowMore && (
          <button
            type="button"
            onClick={() => {
              onShowAll();
              setShowAll(true);
            }}
            className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition"
          >
            View all ({totalReports}) <ArrowRight className="h-3 w-3" />
          </button>
        )}
      </div>
      <div className="space-y-2">
        {totalReports === 0 ? (
          <p className="p-3 text-sm text-slate-500">No reports uploaded yet.</p>
        ) : filteredReports.length === 0 ? (
          <p className="p-3 text-sm text-slate-500">No reports match this filter.</p>
        ) : (
          visible.map((r) => {
            const meta = getCategoryMeta(r.category);
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
                <div className={cn("h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0 text-white", `bg-gradient-to-br ${meta.style.gradient}`)}>
                  {categoryIcon(r.category)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-slate-900 truncate">{r.title}</p>
                  <p className="text-xs text-slate-400">
                    {meta.label} · {formatDate(r.upload_date)}
                  </p>
                </div>
                <span className={cn("text-[11px] font-bold px-2.5 py-1 rounded-full flex-shrink-0", badge.tone)}>{badge.label}</span>
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
    </DashCard>
  );
}

export function RiskFlagsCard({ risks }: { risks: HealthRiskPrediction[] }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? risks : risks.slice(0, RISKS_PREVIEW);

  return (
    <DashCard id="insights">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-black text-slate-900">Risk &amp; Health Flags</h2>
        {!showAll && risks.length > RISKS_PREVIEW && (
          <button type="button" onClick={() => setShowAll(true)} className="text-xs font-semibold text-rose-500 hover:text-rose-600 flex items-center gap-1 transition">
            View all ({risks.length}) <ArrowRight className="h-3 w-3" />
          </button>
        )}
      </div>
      <div className="space-y-3">
        {risks.length === 0 ? (
          <p className="p-3 text-sm text-slate-500">No health risk insights yet.</p>
        ) : (
          visible.map((r) => <RiskRow key={r.id} title={r.risk_title} reason={r.reason} level={r.risk_level} />)
        )}
      </div>
      <div className="mt-4 p-3.5 rounded-xl bg-emerald-50 border border-emerald-100 flex items-start gap-2.5">
        <Shield className="h-4 w-4 text-emerald-600 flex-shrink-0 mt-0.5" />
        <p className="text-xs leading-5 text-emerald-700 font-medium">Please consult your doctor. These insights are not a diagnosis.</p>
      </div>
    </DashCard>
  );
}

function RiskRow({ title, reason, level }: { title: string; reason: string; level: string }) {
  const lv = level.toLowerCase();
  const badgeCls =
    lv === "monitor"
      ? "bg-amber-50 text-amber-700 border-amber-100"
      : lv.includes("low")
        ? "bg-orange-50 text-orange-700 border-orange-100"
        : "bg-rose-50 text-rose-700 border-rose-100";

  return (
    <div className="p-3.5 rounded-2xl border border-rose-50 bg-rose-50/40 hover:border-rose-100 transition">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-slate-900">{title}</p>
          <p className="text-xs text-slate-500 mt-0.5">{reason}</p>
        </div>
        <span className={cn("text-[11px] font-black px-2.5 py-1 rounded-full border flex-shrink-0", badgeCls)}>{level}</span>
      </div>
    </div>
  );
}
