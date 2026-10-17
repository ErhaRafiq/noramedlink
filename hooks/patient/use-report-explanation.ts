"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { AskAnswer, ReportExplanation } from "@/lib/types";

export type ChatMessage =
  | { id: number; role: "patient"; text: string }
  | { id: number; role: "assistant"; text: string; emergency: boolean; source: string; followups: string[]; topics: string[] };

type Status = "loading" | "ready" | "error";

/** A report explained in everyday words, plus the question box about it. Questions are not stored by the app. */
export function useReportExplanation(signedIn: boolean, reportId: number, reloadKey: unknown = null) {
  const [explanation, setExplanation] = useState<ReportExplanation | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const counter = useRef(0);
  const busy = useRef(false);

  useEffect(() => {
    if (!signedIn) return;
    const controller = new AbortController();
    api
      .reportExplanation(reportId, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return;
        setExplanation(data);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Unable to explain this report.");
        setStatus("error");
      });
    return () => controller.abort();
  }, [signedIn, reportId, reloadKey, attempt]);

  const ask = useCallback(
    async (question: string, topic: string | null = null) => {
      const text = question.trim();
      if (!text || busy.current) return false;
      busy.current = true;
      setAsking(true);
      setAskError("");
      const history = messages.slice(-6).map((m) => ({ role: m.role, text: m.text.slice(0, 1500) }));
      setMessages((all) => [...all, { id: ++counter.current, role: "patient", text }]);
      try {
        const reply: AskAnswer = await api.askAboutReport(reportId, { question: text, topic, history });
        setMessages((all) => [
          ...all,
          {
            id: ++counter.current,
            role: "assistant",
            text: reply.answer,
            emergency: reply.emergency,
            source: reply.source,
            followups: reply.followups,
            topics: reply.topics,
          },
        ]);
        return true;
      } catch (err) {
        setAskError(err instanceof Error ? err.message : "The question could not be answered. Please try again.");
        return false;
      } finally {
        busy.current = false;
        setAsking(false);
      }
    },
    [messages, reportId],
  );

  const retry = useCallback(() => {
    setStatus("loading");
    setAttempt((n) => n + 1);
  }, []);
  const clear = useCallback(() => {
    setMessages([]);
    setAskError("");
  }, []);

  return { explanation, status, error, retry, messages, ask, asking, askError, clear };
}
