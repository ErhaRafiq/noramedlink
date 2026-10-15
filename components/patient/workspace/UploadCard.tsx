"use client";

import { useState, type ChangeEvent } from "react";
import { AlertCircle, Camera, CheckCircle2, FilePlus2, Loader2, Sparkles, Upload, X } from "lucide-react";

import { ReportAttention } from "@/components/patient/report/ReportAttention";

import { cn } from "@/lib/cn";
import { UPLOAD_ACCEPT } from "@/lib/image";
import { DEPARTMENTS } from "@/lib/departments";
import { summaryOrigin } from "@/lib/patient-dashboard";
import type { FileQueueItem, useUploadQueue } from "@/hooks/patient/use-upload-queue";
import { DashCard } from "./ui";

type UploadQueue = ReturnType<typeof useUploadQueue>;

export function UploadCard({ upload, onAllUploaded }: { upload: UploadQueue; onAllUploaded: () => void }) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("all");
  const [dragActive, setDragActive] = useState(false);

  const idleCount = upload.queue.filter((i) => i.step === "idle").length;
  const allFinished = upload.queue.length > 0 && upload.queue.every((i) => i.step === "done" || i.step === "error");

  function addFromInput(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) upload.add(Array.from(event.target.files));
    event.target.value = "";
  }

  async function uploadAll() {
    if (await upload.uploadAll({ title, category })) onAllUploaded();
  }

  return (
    <DashCard>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-ink">Upload &amp; Understand with AI</h2>
        <span className="text-[11px] bg-blue-50 text-blue-600 font-semibold px-2.5 py-1 rounded-full border border-blue-100">Max 10 MB each</span>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          upload.add(Array.from(e.dataTransfer.files));
        }}
        className={cn(
          "rounded-card border-2 border-dashed p-6 text-center transition-colors",
          dragActive
            ? "border-blue-400 bg-blue-50"
            : "border-line bg-surface-soft hover:border-blue-300 hover:bg-blue-50/50",
        )}
      >
        <input type="file" multiple accept={UPLOAD_ACCEPT} onChange={addFromInput} className="hidden" id="report-upload" />
        <input type="file" capture="environment" accept="image/*" onChange={addFromInput} className="hidden" id="report-camera" />
        <label htmlFor="report-upload" className="cursor-pointer flex flex-col items-center gap-3">
          <div className="h-14 w-14 rounded-full bg-white border border-blue-100 flex items-center justify-center shadow-sm">
            <Upload className="h-6 w-6 text-blue-500" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-700">Drag &amp; drop files here</p>
            <p className="text-[11px] text-slate-400 mt-0.5">PDF, Word (.docx), JPG, PNG, WEBP, TIFF — multiple files supported; large photos are shrunk</p>
          </div>
          <span className="px-4 py-2 rounded-xl bg-white border border-blue-200 text-sm font-semibold text-blue-600 hover:bg-blue-50 transition shadow-sm">
            Choose Files
          </span>
        </label>
        <label
          htmlFor="report-camera"
          className="inline-flex items-center gap-1.5 mt-2.5 px-3 py-1.5 rounded-xl bg-white border border-blue-100 text-xs font-semibold text-slate-500 hover:border-blue-200 hover:text-blue-700 cursor-pointer transition"
        >
          <Camera className="h-3.5 w-3.5" /> Capture with Camera
        </label>
      </div>

      {upload.queue.length > 0 && (
        <div className="mt-4 space-y-2 max-h-64 overflow-y-auto pr-0.5">
          {upload.queue.map((item) => (
            <UploadQueueRow key={item.id} item={item} onRemove={() => upload.remove(item.id)} />
          ))}
        </div>
      )}

      {idleCount > 0 && (
        <>
          <div className="grid gap-3 mt-4 sm:grid-cols-2">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              aria-label="Report title"
              className="form-field text-sm"
              placeholder="Report title (optional)"
            />
            <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Report category" className="form-field text-sm">
              <option value="all">Auto-detect category</option>
              {DEPARTMENTS.map((d) => (
                <option key={d.slug} value={d.slug}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
          <button type="button" onClick={() => void uploadAll()} disabled={upload.isUploading} className="primary-button w-full mt-3">
            {upload.isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FilePlus2 className="h-4 w-4" />}
            {upload.isUploading ? "Processing..." : `Upload ${idleCount} File(s)`}
          </button>
        </>
      )}

      {allFinished && (
        <button
          type="button"
          onClick={() => {
            upload.clear();
            setTitle("");
          }}
          className="w-full mt-3 py-2.5 rounded-xl border border-slate-200 text-sm font-semibold text-slate-500 hover:bg-slate-50 transition"
        >
          Clear &amp; Upload More
        </button>
      )}
    </DashCard>
  );
}

function UploadQueueRow({ item, onRemove }: { item: FileQueueItem; onRemove: () => void }) {
  const ext = item.file.name.split(".").pop()?.toUpperCase() ?? "FILE";
  const sizeMb = item.file.size / (1024 * 1024);
  const sizeStr = sizeMb < 1 ? `${(item.file.size / 1024).toFixed(0)} KB` : `${sizeMb.toFixed(1)} MB`;
  const isActive = item.step === "uploading";
  const textNotRead = item.report?.ocr_status === "FAILED";
  const origin = summaryOrigin(item.report?.patient_summary_source ?? item.report?.summary_source);

  return (
    <div
      className={cn(
        "flex items-center gap-3 p-3 rounded-2xl border transition",
        item.step === "done"
          ? "border-emerald-100 bg-emerald-50/40"
          : item.step === "error"
            ? "border-rose-100 bg-rose-50/40"
            : isActive
              ? "border-blue-100 bg-blue-50/30"
              : "border-slate-100 bg-white",
      )}
    >
      <div
        className={cn(
          "h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0",
          item.step === "done" ? "bg-emerald-100 text-emerald-600" : item.step === "error" ? "bg-rose-100 text-rose-600" : "bg-blue-100 text-blue-700",
        )}
      >
        {item.step === "done" ? (
          <CheckCircle2 className="h-4 w-4" />
        ) : item.step === "error" ? (
          <AlertCircle className="h-4 w-4" />
        ) : (
          <span className="text-[9px] font-semibold">{ext}</span>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-ink truncate">{item.file.name}</p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-slate-400">{sizeStr}</span>
          {isActive && (
            <span className="text-[11px] text-blue-600 font-semibold flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" />
              Uploading and reading...
            </span>
          )}
          {item.step === "done" &&
            (textNotRead ? (
              <span className="text-[11px] text-amber-700 font-semibold">Saved · text not read</span>
            ) : (
              <span className="text-[11px] text-emerald-600 font-semibold">Saved · text read</span>
            ))}
          {item.step === "error" && (
            <span className="text-[11px] text-rose-600 font-semibold truncate max-w-[160px]">{item.error ?? "Upload failed"}</span>
          )}
        </div>
        {isActive && (
          <div className="mt-1.5 h-1 rounded-full bg-blue-100 overflow-hidden">
            {/* Indeterminate: the request reports no progress, so no percentage is shown. */}
            <div className="h-full w-full animate-pulse rounded-full bg-gradient-to-r from-brand-blue to-brand-teal" />
          </div>
        )}
        {item.step === "done" && (
          <div className="mt-1.5 h-1 rounded-full bg-emerald-200 overflow-hidden">
            <div className="h-full w-full rounded-full bg-emerald-500" />
          </div>
        )}
        {item.step === "done" && item.report?.patient_summary && (
          <div className="mt-3 p-3 rounded-xl bg-white border border-emerald-100 shadow-sm relative">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Sparkles className="h-3.5 w-3.5 text-emerald-500" />
              <p className="text-xs font-semibold text-slate-800">{origin.label}</p>
            </div>
            <p className="max-h-60 overflow-y-auto whitespace-pre-line text-xs leading-relaxed text-slate-600">{item.report.patient_summary}</p>
            <p className="mt-1.5 text-[11px] text-ink-muted">
              {origin.note}
            </p>
          </div>
        )}
        {item.step === "done" && item.report && <ReportAttention report={item.report} compact />}
      </div>

      {item.step === "idle" && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${item.file.name}`}
          className="h-7 w-7 rounded-lg border border-slate-200 flex items-center justify-center text-slate-400 hover:text-rose-500 hover:border-rose-200 transition flex-shrink-0"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
