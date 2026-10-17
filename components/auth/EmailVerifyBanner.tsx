"use client";

import { useEffect, useState } from "react";
import { MailCheck } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";

/**
 * Shown while the account's email address is not confirmed. Nothing is blocked: the account works, but
 * appointment confirmations and reminders are only emailed to a confirmed address. The server allows one new
 * link a minute (3 an hour), and says how long to wait.
 */
export function EmailVerifyBanner({ verified, className }: { verified: boolean; className?: string }) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [wait, setWait] = useState(0);

  useEffect(() => {
    if (wait <= 0) return;
    const timer = window.setTimeout(() => setWait((seconds) => seconds - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [wait]);

  if (verified) return null;

  async function resend() {
    if (busy || wait > 0) return;
    setBusy(true);
    setNotice(null);
    try {
      const answer = await api.resendVerification();
      setNotice({ tone: "success", text: answer.message });
      setWait(60);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429 && err.retryAfterSeconds) setWait(err.retryAfterSeconds);
      setNotice({ tone: "error", text: err instanceof Error ? err.message : "The link could not be sent. Please try again." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Alert tone="warning" title="Confirm your email address" className={className}>
      <p>We sent a confirmation link to your email. Until you use it, we cannot email you appointment confirmations or reminders.</p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button size="sm" variant="secondary" loading={busy} disabled={busy || wait > 0} icon={<MailCheck className="h-4 w-4" />} onClick={() => void resend()}>
          {busy ? "Sending..." : wait > 0 ? `Send a new link in ${wait} s` : "Send a new link"}
        </Button>
        {notice ? (
          <span role={notice.tone === "error" ? "alert" : "status"} className="text-xs font-medium">
            {notice.text}
          </span>
        ) : null}
      </div>
    </Alert>
  );
}
