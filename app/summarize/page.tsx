"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

type SummaryResponse = {
  summary: string;
  key_findings: string[];
  risk_indicators: string[];
  recommendations: string[];
  warning?: string | null;
};

const exampleReport = `CBC report: Hemoglobin 10.8 g/dL, WBC 13.2, Platelets 230. Patient has fever and cough for 3 days. No chest pain. Blood pressure 145/92. Glucose 186 mg/dL. Impression: possible infection, follow clinical correlation.`;

function ResultList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="dashboard-panel">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-lg font-black text-slate-950">{title}</h2>
        <span className="soft-badge">{items.length}</span>
      </div>
      {items.length > 0 ? (
        <ul className="space-y-3">
          {items.map((item) => (
            <li
              key={item}
              className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">No items detected.</p>
      )}
    </section>
  );
}

export default function SummarizePage() {
  const [text, setText] = useState("");
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSummarizingSavedReports, setIsSummarizingSavedReports] = useState(false);

  function getStoredUserId() {
    if (typeof window === "undefined") {
      return "";
    }

    return localStorage.getItem("userId") ?? "";
  }

  async function summarizeSavedReports() {
    setStatusMessage("");
    setSummary(null);

    const userId = getStoredUserId();

    if (!userId) {
      setStatusMessage("Login as a patient before summarizing saved reports.");
      return;
    }

    setIsSummarizingSavedReports(true);

    try {
      const response = await fetch("/api/summarize", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ userId }),
      });
      const data = (await response.json()) as SummaryResponse & { message?: string };

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to summarize saved reports.");
        return;
      }

      setText("");
      setSummary(data);
      setStatusMessage(data.warning ?? "Summary generated from saved patient reports.");
    } catch {
      setStatusMessage("Unable to reach the summarization service.");
    } finally {
      setIsSummarizingSavedReports(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatusMessage("");
    setSummary(null);

    if (text.trim().length < 20) {
      setStatusMessage("Enter at least 20 characters of report text.");
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch("/api/summarize", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text }),
      });
      const data = (await response.json()) as SummaryResponse & { message?: string };

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to summarize this report.");
        return;
      }

      setSummary(data);
      if (data.warning) {
        setStatusMessage(data.warning);
      }
    } catch {
      setStatusMessage("Unable to reach the summarization service.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="app-shell min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-6xl">
        <div className="dashboard-topbar flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <Link href="/" className="section-eyebrow">
              Nora MedLink
            </Link>
            <h1 className="section-title mt-3">Medical Summarizer</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-500">
              Summarize saved patient reports or paste report text manually.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/dashboard" className="secondary-button px-4 py-2">
              Dashboard
            </Link>
            <Link href="/doctors" className="gradient-button px-4 py-2">
              Find Doctors
            </Link>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <form className="dashboard-panel" onSubmit={handleSubmit}>
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <p className="section-eyebrow">Input</p>
                <h2 className="mt-2 text-2xl font-black text-slate-950">
                  Patient Report Data
                </h2>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <button
                  type="button"
                  onClick={summarizeSavedReports}
                  disabled={isSummarizingSavedReports}
                  className="gradient-button px-4 py-2"
                >
                  {isSummarizingSavedReports ? "Reading..." : "Use Saved Reports"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setText(exampleReport);
                    setStatusMessage("");
                  }}
                  className="secondary-button px-4 py-2"
                >
                  Use Example
                </button>
              </div>
            </div>

            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              className="min-h-[360px] w-full resize-y rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-7 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-teal-500 focus:ring-4 focus:ring-teal-100"
              placeholder="Click Use Saved Reports, or paste CBC, LFT, KFT, prescription notes, or discharge summary text..."
            />

            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs font-semibold text-slate-500">
                {text.trim().length} characters
              </p>
              <button type="submit" disabled={isSubmitting} className="gradient-button">
                {isSubmitting ? "Summarizing..." : "Generate Summary"}
              </button>
            </div>

            {statusMessage ? (
              <p className="mt-4 rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800">
                {statusMessage}
              </p>
            ) : null}
          </form>

          <div className="space-y-6">
            <section className="dashboard-panel border-teal-100 bg-teal-50/60">
              <p className="section-eyebrow">Output</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">
                Structured Summary
              </h2>
              <p className="mt-4 rounded-xl bg-white px-4 py-4 text-sm leading-7 text-slate-700 shadow-sm">
                {summary?.summary || "Your summary will appear here after analysis."}
              </p>
            </section>

            {summary ? (
              <div className="grid gap-6">
                <ResultList title="Key Findings" items={summary.key_findings} />
                <ResultList title="Risk Indicators" items={summary.risk_indicators} />
                <ResultList title="Recommendations" items={summary.recommendations} />
              </div>
            ) : (
              <section className="dashboard-panel">
                <div className="grid gap-3 sm:grid-cols-3">
                  {["Numbers preserved", "Negations detected", "No diagnosis added"].map((item) => (
                    <div key={item} className="rounded-xl bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700">
                      {item}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
