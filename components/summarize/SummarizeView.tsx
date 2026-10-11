"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { FileStack, FileText, Sparkles } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { api } from "@/lib/api";
import { summarizeMedicalText } from "@/lib/medical-summarizer";
import { useStoredSession } from "@/hooks/use-stored-session";
import { SummaryResult, type SummaryView } from "./SummaryResult";

const MIN_LENGTH = 20;
const EXAMPLE_REPORT =
  "CBC report: Hemoglobin 10.8 g/dL, WBC 13.2, Platelets 230. Patient has fever and cough for 3 days. No chest pain. Blood pressure 145/92. Glucose 186 mg/dL. Impression: possible infection, follow clinical correlation.";

/** Server summary text combined with the local rule-based breakdown (findings, values, steps). */
function toView(text: string, backend: { summary: string; warning: string | null }): SummaryView {
  return { ...summarizeMedicalText(text), summary: backend.summary, warning: backend.warning };
}

export function SummarizeView() {
  const { ready, session } = useStoredSession();
  const isPatient = session?.user.role === "patient";
  const [text, setText] = useState("");
  const [result, setResult] = useState<SummaryView | null>(null);
  const [pending, setPending] = useState<"text" | "saved" | null>(null);
  const [error, setError] = useState("");

  async function summarizeText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || pending) return;
    setError("");
    const input = text.trim();
    if (input.length < MIN_LENGTH) {
      setError(`Enter at least ${MIN_LENGTH} characters of report text.`);
      return;
    }
    setPending("text");
    setResult(null);
    try {
      setResult(toView(input, await api.summarizeText(session.token, input)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The summary could not be generated.");
    } finally {
      setPending(null);
    }
  }

  async function summarizeSavedReports() {
    if (!session || pending) return;
    setError("");
    setPending("saved");
    setResult(null);
    try {
      const backend = await api.summarizeSavedReports(session.token);
      setText("");
      setResult(toView(backend.text, backend));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Your saved reports could not be summarized.");
    } finally {
      setPending(null);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Summaries"
        title="Summarize a medical report"
        description="Paste the text of a lab report or prescription, or summarize the reports you have already uploaded."
      />

      {!ready ? null : !session ? (
        <EmptyState
          icon={Sparkles}
          title="Sign in to summarize reports"
          description="Summaries are generated for signed-in users."
          action={
            <Link href="/login" className="secondary-button min-h-[36px] px-3 text-xs">
              Sign in
            </Link>
          }
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
          <form onSubmit={summarizeText} className="h-fit rounded-card border border-line bg-white p-5 shadow-card sm:p-6" noValidate>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label htmlFor="report-text" className="text-base font-semibold text-ink">
                Report text
              </label>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" icon={<FileText className="h-4 w-4" />} onClick={() => setText(EXAMPLE_REPORT)}>
                  Use example
                </Button>
                {isPatient ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={pending === "saved"}
                    disabled={pending !== null}
                    icon={<FileStack className="h-4 w-4" />}
                    onClick={() => void summarizeSavedReports()}
                  >
                    {pending === "saved" ? "Reading reports..." : "My saved reports"}
                  </Button>
                ) : null}
              </div>
            </div>
            <textarea
              id="report-text"
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={14}
              placeholder="Paste CBC, LFT, KFT, prescription or discharge summary text..."
              className="form-field mt-3 min-h-[320px] resize-y leading-7"
            />
            <div className="mt-3 flex items-center justify-between gap-3">
              <p className="text-xs text-ink-muted">{text.trim().length} characters</p>
              <Button type="submit" loading={pending === "text"} disabled={pending !== null} icon={<Sparkles className="h-4 w-4" />}>
                {pending === "text" ? "Summarizing..." : "Summarize"}
              </Button>
            </div>
            {error ? <Alert tone="error" className="mt-4">{error}</Alert> : null}
          </form>

          <SummaryResult result={result} loading={pending !== null} />
        </div>
      )}
    </PageContainer>
  );
}
