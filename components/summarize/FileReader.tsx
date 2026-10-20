"use client";

import { useRef, type ChangeEvent } from "react";
import { Camera, FileUp, Loader2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { FileTextState } from "@/hooks/use-file-text";
import { UPLOAD_ACCEPT } from "@/lib/image";

/** Pick a PDF, Word file or a photo of a report: its text is read here (nothing is saved) and put in the box below
 * for the person to check before summarising. */
export function FileReader({ state, onPick, disabled }: { state: FileTextState; onPick: (file: File) => void; disabled: boolean }) {
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const reading = state.status === "reading";

  function picked(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // the same file can be picked again
    if (file) onPick(file);
  }

  return (
    <div className="mt-3 rounded-control border border-dashed border-line bg-surface-soft p-4">
      <input ref={fileInput} type="file" accept={UPLOAD_ACCEPT} onChange={picked} className="hidden" aria-label="Choose a report file" />
      <input ref={cameraInput} type="file" accept="image/*" capture="environment" onChange={picked} className="hidden" aria-label="Take a photo of the report" />
      <p className="text-sm font-medium text-ink">Have the report as a file or a photo?</p>
      <p className="mt-0.5 text-xs leading-5 text-ink-muted">
        PDF, Word, or a photo (JPG, PNG, iPhone HEIC), up to 10 MB. The text is read on our server and nothing is saved.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" disabled={disabled || reading} icon={<FileUp className="h-4 w-4" />} onClick={() => fileInput.current?.click()}>
          Choose a file
        </Button>
        <Button variant="secondary" size="sm" disabled={disabled || reading} icon={<Camera className="h-4 w-4" />} onClick={() => cameraInput.current?.click()}>
          Take a photo
        </Button>
      </div>
      <ul className="mt-3 list-disc space-y-0.5 pl-5 text-xs leading-5 text-ink-muted">
        <li>Lay the page flat, in good light, with no shadow.</li>
        <li>Keep the whole page in the picture and hold the phone steady.</li>
      </ul>

      {reading ? (
        <p role="status" className="mt-3 flex items-center gap-2 text-sm text-ink-muted">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          <span className="min-w-0 break-words">Reading {state.fileName}... a photo can take up to a minute.</span>
        </p>
      ) : null}
      {state.status === "error" ? (
        <Alert tone="error" className="mt-3">
          {state.message}
        </Alert>
      ) : null}
      {state.status === "done" ? (
        <Alert tone={state.result.uncertain_count > 0 ? "warning" : "success"} className="mt-3" title={`Read ${state.fileName}`}>
          <p>The text is in the box below. Please check it against your report and fix anything that is wrong before you summarise.</p>
          {state.result.truncated ? <p className="mt-1">The file was long, so only the first part was kept.</p> : null}
          {state.result.uncertain_count > 0 ? (
            <>
              <p className="mt-1">These numbers may have been misread, so check them against the original report:</p>
              <ul className="mt-1 list-disc space-y-0.5 break-words pl-5">
                {state.result.uncertain.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          ) : null}
        </Alert>
      ) : null}
    </div>
  );
}
