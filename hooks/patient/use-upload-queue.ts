"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { MAX_UPLOAD_BYTES, shrinkLargeImage } from "@/lib/image";
import type { MedicalDocument } from "@/lib/types";
import type { Notify } from "@/hooks/use-toast";

export type UploadStep = "idle" | "uploading" | "ocr" | "ai" | "saving" | "done" | "error";
export type FileQueueItem = {
  id: string;
  file: File;
  step: UploadStep;
  error?: string;
  report?: MedicalDocument;
};
export type UploadOptions = { title: string; notes: string; category: string };

// The server does upload, OCR, AI and save in one request; these steps only show progress.
const STEP_ORDER: UploadStep[] = ["uploading", "ocr", "ai", "saving"];
const STEP_INTERVAL_MS = 2800;

function newId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

/** Queue of report files to upload one after another, with per-file progress and errors. */
export function useUploadQueue({
  token,
  notify,
  onUploaded,
}: {
  token: string | null;
  notify: Notify;
  onUploaded: (report: MedicalDocument) => void;
}) {
  const [queue, setQueue] = useState<FileQueueItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const tickersRef = useRef(new Set<number>());

  useEffect(() => {
    const tickers = tickersRef.current;
    return () => tickers.forEach((ticker) => window.clearInterval(ticker));
  }, []);

  const add = useCallback(
    (files: File[]) => {
      const valid: FileQueueItem[] = [];
      let skipped = 0;
      for (const file of files) {
        // Images over the limit may still fit once shrunk; anything else is skipped now.
        if (file.size > MAX_UPLOAD_BYTES && !file.type.startsWith("image/")) {
          skipped++;
          continue;
        }
        valid.push({ id: newId(), file, step: "idle" });
      }
      if (skipped > 0) notify("error", `${skipped} file(s) exceeded the 10 MB limit and were skipped.`);
      if (valid.length > 0) setQueue((prev) => [...prev, ...valid]);
    },
    [notify],
  );

  const remove = useCallback((id: string) => setQueue((prev) => prev.filter((item) => item.id !== id)), []);
  const clear = useCallback(() => setQueue([]), []);

  const uploadOne = useCallback(
    async (item: FileQueueItem, activeToken: string, options: UploadOptions) => {
      const update = (patch: Partial<FileQueueItem>) =>
        setQueue((prev) => prev.map((i) => (i.id === item.id ? { ...i, ...patch } : i)));

      update({ step: "uploading" });
      let stepIndex = 0;
      const ticker = window.setInterval(() => {
        stepIndex = Math.min(stepIndex + 1, STEP_ORDER.length - 1);
        setQueue((prev) =>
          prev.map((i) => (i.id !== item.id || i.step === "done" || i.step === "error" ? i : { ...i, step: STEP_ORDER[stepIndex] })),
        );
      }, STEP_INTERVAL_MS);
      tickersRef.current.add(ticker);

      try {
        const file = await shrinkLargeImage(item.file);
        if (file !== item.file) update({ file });
        if (file.size > MAX_UPLOAD_BYTES) throw new Error("File is larger than 10 MB.");
        const formData = new FormData();
        formData.append("file", file);
        formData.append("title", options.title.trim());
        formData.append("notes", options.notes.trim());
        // "auto" lets the backend detect the department from the text ("general" would pin it).
        formData.append("category", options.category === "all" ? "auto" : options.category);
        const report = await api.uploadReport(activeToken, formData);
        onUploaded(report);
        update({ step: "done", report });
        if (report.ocr_status === "FAILED") {
          notify("info", `${report.title} was saved, but its text could not be read. Open the report to type it in.`);
        } else {
          notify("success", `${report.title} uploaded and its text was read.`);
        }
      } catch (err) {
        update({ step: "error", error: err instanceof Error ? err.message : "Upload failed" });
      } finally {
        window.clearInterval(ticker);
        tickersRef.current.delete(ticker);
      }
    },
    [notify, onUploaded],
  );

  /** Uploads every idle file in order. Returns true when something was uploaded. */
  const uploadAll = useCallback(
    async (options: UploadOptions) => {
      if (!token) {
        notify("error", "Please sign in again before uploading.");
        return false;
      }
      const idle = queue.filter((item) => item.step === "idle");
      if (idle.length === 0 || isUploading) return false;
      setIsUploading(true);
      try {
        for (const item of idle) {
          await uploadOne(item, token, options);
        }
      } finally {
        setIsUploading(false);
      }
      return true;
    },
    [isUploading, notify, queue, token, uploadOne],
  );

  return { queue, isUploading, add, remove, clear, uploadAll };
}
