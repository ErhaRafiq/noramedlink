"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { PhoneCall, Send, Trash2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { useReportExplanation } from "@/hooks/patient/use-report-explanation";

type Chat = ReturnType<typeof useReportExplanation>;

/** "Ask about this report": questions are answered from the report's own values by fixed rules; an AI may only
 * re-word the answer. Nothing typed here is saved. Emergencies get the 1122 message and nothing else. */
export function ReportAsk({ chat, suggestions, disclaimer }: { chat: Chat; suggestions: string[]; disclaimer: string }) {
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const last = chat.messages[chat.messages.length - 1];
  const next = last?.role === "assistant" ? last.followups : suggestions;

  useEffect(() => {
    if (chat.messages.length) endRef.current?.scrollIntoView({ block: "nearest" });
  }, [chat.messages.length]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (await chat.ask(text)) setText("");
  }

  return (
    <section aria-label="Ask about this report" className="rounded-control border border-line bg-surface-soft p-4">
      <h3 className="text-sm font-semibold text-ink">Want more explained? Ask about this report</h3>
      <p className="mt-0.5 text-xs leading-5 text-ink-muted">{disclaimer} Your questions are not saved.</p>

      {chat.messages.length > 0 ? (
        <div className="mt-3 space-y-3" aria-live="polite">
          {chat.messages.map((m) =>
            m.role === "patient" ? (
              <p key={m.id} className="ml-auto max-w-[85%] break-words rounded-control bg-brand-blue px-3 py-2 text-sm text-white">
                {m.text}
              </p>
            ) : (
              <div
                key={m.id}
                className={`max-w-[95%] rounded-control border p-3 ${m.emergency ? "border-rose-300 bg-rose-50" : "border-line bg-white"}`}
              >
                {m.emergency ? (
                  <p className="mb-1 flex items-center gap-2 text-sm font-semibold text-rose-900">
                    <PhoneCall className="h-4 w-4" aria-hidden /> Emergency
                  </p>
                ) : null}
                <p className="whitespace-pre-line break-words text-sm leading-6 text-ink">{m.text}</p>
                <p className="mt-2 text-xs text-ink-muted">
                  {m.emergency
                    ? "This is not an emergency service."
                    : m.source === "rules"
                      ? "Written by a computer from your report, by fixed rules. Can be wrong."
                      : "Written by a computer and checked against your report. Can be wrong."}
                </p>
              </div>
            ),
          )}
          {chat.asking ? (
            <p role="status" className="flex items-center gap-2 text-sm text-ink-muted">
              <Spinner className="h-4 w-4" /> Looking at your report...
            </p>
          ) : null}
          <div ref={endRef} />
        </div>
      ) : null}

      {chat.askError ? (
        <Alert tone="error" className="mt-3">
          {chat.askError}
        </Alert>
      ) : null}

      {next.length > 0 && !chat.asking ? (
        <div className="mt-3 flex flex-wrap gap-2" aria-label="Suggested questions">
          {next.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => void chat.ask(q)}
              className="rounded-full border border-line bg-white px-3 py-1.5 text-left text-xs font-medium text-slate-700 transition duration-200 hover:border-brand-blue hover:text-brand-blue"
            >
              {q}
            </button>
          ))}
        </div>
      ) : null}

      <form onSubmit={submit} className="mt-3 flex flex-col gap-2 sm:flex-row">
        <label htmlFor="report-question" className="sr-only">
          Your question about this report
        </label>
        <input
          id="report-question"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={500}
          placeholder="For example: what does my hemoglobin mean?"
          className="min-h-[44px] min-w-0 flex-1 rounded-control border border-line bg-white px-3 text-sm focus-visible:shadow-focus focus-visible:outline-none"
        />
        <Button type="submit" loading={chat.asking} disabled={text.trim().length < 3} icon={<Send className="h-4 w-4" aria-hidden />}>
          {chat.asking ? "Asking..." : "Ask"}
        </Button>
      </form>
      {chat.messages.length > 0 ? (
        <Button variant="ghost" size="sm" className="mt-2" onClick={chat.clear} disabled={chat.asking}>
          <Trash2 className="h-4 w-4" aria-hidden />
          Clear this conversation
        </Button>
      ) : null}
    </section>
  );
}
