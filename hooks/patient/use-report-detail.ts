"use client";

import { useCallback, useEffect, useState } from "react";

import { api, isApiError } from "@/lib/api";
import { toDepartmentSlug } from "@/lib/departments";
import type { MedicalDocument } from "@/lib/types";

type Status = "loading" | "ready" | "not-found" | "error";
type Pending = "save" | "regenerate" | "delete" | null;
export type ActionResult = { ok: true; message: string } | { ok: false; message: string };

function editableTextOf(report: MedicalDocument) {
  return report.extracted_text ?? report.ocr_cleaned_text ?? "";
}

/** One report for the signed-in patient: load, edit text and department, re-run OCR, delete. */
export function useReportDetail(token: string | null, reportId: number) {
  const [report, setReport] = useState<MedicalDocument | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [department, setDepartment] = useState("general");
  const [pending, setPending] = useState<Pending>(null);

  const apply = useCallback((data: MedicalDocument) => {
    setReport(data);
    setText(editableTextOf(data));
    setDepartment(toDepartmentSlug(data.department_slug ?? data.category));
  }, []);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    api
      .patientDocument(token, reportId)
      .then((data) => {
        if (controller.signal.aborted) return;
        apply(data);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        if (isApiError(err, 404)) {
          setStatus("not-found");
          return;
        }
        setError(err instanceof Error ? err.message : "Unable to load this report.");
        setStatus("error");
      });
    return () => controller.abort();
  }, [apply, reportId, token]);

  const isDirty = report !== null && (text !== editableTextOf(report) || department !== toDepartmentSlug(report.department_slug ?? report.category));

  const save = useCallback(async (): Promise<ActionResult> => {
    if (!token || !report || pending) return { ok: false, message: "Please wait for the current action to finish." };
    if (!text.trim()) return { ok: false, message: "The report text cannot be empty." };
    setPending("save");
    try {
      apply(await api.updateDocument(token, report.id, { department, extracted_text: text }));
      return { ok: true, message: "Your edits were saved and the summary was updated." };
    } catch (err) {
      return { ok: false, message: err instanceof Error ? err.message : "Unable to save your edits." };
    } finally {
      setPending(null);
    }
  }, [apply, department, pending, report, text, token]);

  const regenerate = useCallback(async (): Promise<ActionResult> => {
    if (!token || !report || pending) return { ok: false, message: "Please wait for the current action to finish." };
    setPending("regenerate");
    try {
      const updated = await api.regenerateDocumentOcr(token, report.id);
      apply(updated);
      return updated.ocr_status === "FAILED"
        ? { ok: false, message: "Reading the file again failed. Your report was kept as it was." }
        : { ok: true, message: "The file was read again and the summary was updated." };
    } catch (err) {
      return { ok: false, message: err instanceof Error ? err.message : "Unable to read the file again." };
    } finally {
      setPending(null);
    }
  }, [apply, pending, report, token]);

  /** Deletes the report. Resolves true on success (the caller then navigates away). */
  const remove = useCallback(async (): Promise<ActionResult> => {
    if (!token || !report || pending) return { ok: false, message: "Please wait for the current action to finish." };
    setPending("delete");
    try {
      await api.deleteDocument(token, report.id);
      return { ok: true, message: "Report deleted." };
    } catch (err) {
      setPending(null);
      return { ok: false, message: err instanceof Error ? err.message : "Unable to delete the report." };
    }
  }, [pending, report, token]);

  return { report, status, error, text, setText, department, setDepartment, isDirty, pending, save, regenerate, remove };
}
