"use client";

import { useCallback, useState } from "react";
import { Copy, KeyRound } from "lucide-react";

import { Button } from "@/components/ui/button";
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
    <section id="care-team" className="scroll-mt-24">
      <DashCard>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-control bg-teal-50 text-teal-700">
              <KeyRound className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <h2 className="text-base font-semibold text-ink">Share your records with a doctor</h2>
              <p className="mt-0.5 max-w-xl text-sm leading-6 text-ink-muted">
                Give your doctor a one-time code. It opens your vitals, reports and medicines for one consultation.
              </p>
            </div>
          </div>
          <Button loading={generate.pending} icon={<KeyRound className="h-4 w-4" />} onClick={() => void generate.run()} className="flex-shrink-0">
            {generate.pending ? "Generating..." : otp ? "New code" : "Generate code"}
          </Button>
        </div>
        {otp && (
          <div className="mt-4 flex flex-col gap-3 rounded-control border border-teal-100 bg-teal-50/70 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-teal-800">One-time code</p>
              <p className="mt-1 font-mono text-2xl font-semibold tracking-[0.3em] text-ink">{otp.code}</p>
              <p className="mt-1 text-xs text-ink-muted">Expires {formatDateTime(otp.expiresAt)}</p>
            </div>
            <Button variant="secondary" size="sm" icon={<Copy className="h-4 w-4" />} onClick={() => void copyCode()} className="self-start sm:self-center">
              Copy
            </Button>
          </div>
        )}
      </DashCard>
    </section>
  );
}
