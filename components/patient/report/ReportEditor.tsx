"use client";

import type { FormEvent } from "react";
import { RefreshCw, Save, Trash2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SelectField, TextAreaField } from "@/components/ui/field";
import { DEPARTMENTS } from "@/lib/departments";
import type { useReportDetail } from "@/hooks/patient/use-report-detail";
import { ReportCard } from "./ReportSections";

type Detail = ReturnType<typeof useReportDetail>;

/** Correct the text and department, re-read the file, or delete the report. */
export function ReportEditor({
  detail,
  onSave,
  onRegenerate,
  onDelete,
}: {
  detail: Detail;
  onSave: () => void;
  onRegenerate: () => void;
  onDelete: () => void;
}) {
  const busy = detail.pending !== null;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave();
  }

  return (
    <ReportCard title="Correct the report" description="Fix any reading mistakes; the summary is rebuilt from your text when you save.">
      <form className="space-y-4" onSubmit={submit}>
        <SelectField label="Department" value={detail.department} onChange={(event) => detail.setDepartment(event.target.value)}>
          {DEPARTMENTS.map((item) => (
            <option key={item.slug} value={item.slug}>
              {item.label}
            </option>
          ))}
        </SelectField>
        <TextAreaField
          label="Report text"
          rows={14}
          className="min-h-[320px] font-mono text-xs leading-6 sm:text-sm"
          value={detail.text}
          onChange={(event) => detail.setText(event.target.value)}
        />
        <Alert tone="warning">Text read from a photo can contain mistakes. Check important values against the original file.</Alert>
        <div className="grid gap-2 sm:grid-cols-3">
          <Button type="submit" loading={detail.pending === "save"} disabled={busy || !detail.isDirty} icon={<Save className="h-4 w-4" />}>
            {detail.pending === "save" ? "Saving..." : "Save changes"}
          </Button>
          <Button variant="secondary" loading={detail.pending === "regenerate"} disabled={busy} icon={<RefreshCw className="h-4 w-4" />} onClick={onRegenerate}>
            {detail.pending === "regenerate" ? "Reading..." : "Read file again"}
          </Button>
          <Button variant="danger" disabled={busy} icon={<Trash2 className="h-4 w-4" />} onClick={onDelete}>
            Delete report
          </Button>
        </div>
      </form>
    </ReportCard>
  );
}
