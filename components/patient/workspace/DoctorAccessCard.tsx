"use client";

import { useCallback, useState } from "react";
import { Copy, KeyRound, Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import { useAsyncAction } from "@/hooks/use-async-action";
import type { Notify } from "@/hooks/use-toast";
import { formatDateTime } from "./helpers";
import { DashCard } from "./ui";

/** One-time code the patient gives a doctor to open their dashboard for one consultation. */
export function DoctorAccessCard({ token, notify }: { token: string; notify: Notify }) {
  const [otp, setOtp] = useState<{ code: string; expiresAt: string } | null>(null);

  const generate = useAsyncAction(
    useCallback(async () => {
      try {
        const data = await api.issueDashboardOtp(token);
        setOtp(data.otp);
        notify("success", "One-time code generated. Share it only with your doctor.");
      } catch (err) {
        notify("error", err instanceof Error ? err.message : "Unable to generate a code.");
      }
    }, [notify, token]),
  );

  async function copyCode() {
    if (!otp) return;
    try {
      await navigator.clipboard.writeText(otp.code);
      notify("success", "Code copied. It works once and expires soon.");
    } catch {
      notify("info", `Your one-time code is ${otp.code}`);
    }
  }

  return (
    <section id="care-team">
      <DashCard>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-teal-400 to-blue-500 flex items-center justify-center shadow-md shadow-teal-200/50 flex-shrink-0">
              <KeyRound className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900">Share your dashboard with a doctor</h2>
              <p className="text-xs text-slate-500 mt-0.5 max-w-xl">
                Generate a one-time code and give it to your doctor. It unlocks your vitals, reports and medicines for one
                consultation, and you can generate a new code at any time.
              </p>
            </div>
          </div>
          <button type="button" onClick={() => void generate.run()} disabled={generate.pending} className="primary-button flex-shrink-0">
            {generate.pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
            {generate.pending ? "Generating..." : otp ? "New Code" : "Generate Code"}
          </button>
        </div>
        {otp && (
          <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-teal-100 bg-teal-50/60 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-teal-700">One-time code</p>
              <p className="mt-1 font-mono text-2xl font-black tracking-[0.3em] text-slate-900">{otp.code}</p>
              <p className="text-xs text-slate-500 mt-1">Expires {formatDateTime(otp.expiresAt)}</p>
            </div>
            <button
              type="button"
              onClick={copyCode}
              className="inline-flex items-center gap-1.5 self-start rounded-xl border border-teal-200 bg-white px-4 py-2 text-sm font-bold text-teal-700 hover:bg-teal-50 transition sm:self-center"
            >
              <Copy className="h-4 w-4" /> Copy
            </button>
          </div>
        )}
      </DashCard>
    </section>
  );
}
